from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.db.models import Chat, Message, MessageRole, AITask, TaskStatus, TaskType, User
from server.modules.ai_orchestrator.nexus_agent import (
    extract_with_langgraph,
    is_cancellation_text,
    is_confirmation_text,
)
from server.modules.billing.service import assert_external_query_quota, assert_lead_quota
from server.workers.tasks import run_market_task, run_scrape_task


def _canonical_id(raw: str) -> str:
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(raw).strip()


def _message_to_dict(message: Message) -> dict:
    return {
        "id": str(message.id),
        "chat_id": str(message.chat_id),
        "role": message.role.value,
        "content": message.content,
        "tool_calls": message.tool_calls or None,
        "metadata": {"tool_calls": message.tool_calls or None},
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _chat_to_dict(chat: Chat) -> dict:
    return {
        "id": str(chat.id),
        "title": chat.title,
        "awaiting_confirmation": chat.awaiting_confirmation,
        "created_at": chat.created_at.isoformat() if chat.created_at else None,
        "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
    }


def _task_to_dict(task: AITask) -> dict:
    return {
        "id": str(task.id),
        "chat_id": str(task.chat_id) if task.chat_id else None,
        "task_type": task.task_type.value,
        "status": task.status.value,
        "progress": task.progress,
        "requested_quantity": task.requested_quantity,
        "completed_quantity": task.completed_quantity,
        "prompt": task.prompt,
        "parsed_payload": task.parsed_payload or {},
        "result_payload": task.result_payload or {},
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _get_chat(db: Session, user: User, chat_id: str) -> Chat:
    parsed_chat_id = _canonical_id(chat_id)
    chat = db.query(Chat).filter(Chat.id == parsed_chat_id, Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


def _latest_chat(db: Session, user: User) -> Chat | None:
    return db.query(Chat).filter(Chat.user_id == user.id).order_by(Chat.updated_at.desc(), Chat.created_at.desc()).first()


def _get_or_create_chat(db: Session, user: User, chat_id: str | None) -> Chat:
    if chat_id:
        return _get_chat(db, user, chat_id)

    latest = _latest_chat(db, user)
    if latest:
        return latest

    chat = Chat(user_id=user.id, title="Nova conversa")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def _save_message(
    db: Session,
    *,
    chat: Chat,
    role: MessageRole,
    content: str,
    tool_calls: list | dict | None = None,
) -> Message:
    row = Message(
        chat_id=chat.id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    db.add(row)

    chat.updated_at = row.created_at  # type: ignore[assignment]
    db.add(chat)

    db.commit()
    db.refresh(row)
    return row


def _ensure_chat_title(db: Session, chat: Chat, user_message: str) -> None:
    if chat.title and chat.title != "Nova conversa":
        return
    title = user_message.strip()
    if not title:
        return
    chat.title = title[:64] + ("..." if len(title) > 64 else "")
    db.add(chat)
    db.commit()


def _create_task(
    db: Session,
    user: User,
    chat: Chat,
    *,
    task_type: TaskType,
    prompt: str,
    parsed_payload: dict,
    requested_quantity: int,
) -> AITask:
    task = AITask(
        user_id=user.id,
        chat_id=chat.id,
        task_type=task_type,
        status=TaskStatus.queued,
        progress=0,
        prompt=prompt,
        parsed_payload=parsed_payload,
        requested_quantity=requested_quantity,
        completed_quantity=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_chat(db: Session, user: User, title: str | None = None) -> dict:
    chat = Chat(user_id=user.id, title=(title or "Nova conversa")[:240])
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return _chat_to_dict(chat)


def list_chats(db: Session, user: User, limit: int = 50) -> list[dict]:
    rows = (
        db.query(Chat)
        .filter(Chat.user_id == user.id)
        .order_by(Chat.updated_at.desc(), Chat.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_chat_to_dict(item) for item in rows]


def list_messages(db: Session, user: User, limit: int = 60, chat_id: str | None = None) -> list[dict]:
    chat = _get_or_create_chat(db, user, chat_id)
    rows = (
        db.query(Message)
        .filter(Message.chat_id == chat.id)
        .order_by(Message.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_message_to_dict(item) for item in reversed(rows)]


def clear_messages(db: Session, user: User, chat_id: str | None = None) -> int:
    chat = _get_or_create_chat(db, user, chat_id)
    deleted = db.query(Message).filter(Message.chat_id == chat.id).delete(synchronize_session=False)
    chat.awaiting_confirmation = False
    chat.pending_action = None
    db.add(chat)
    db.commit()
    return int(deleted)


def _confirm_or_execute_pending(
    db: Session,
    user: User,
    chat: Chat,
    user_message: Message,
    text: str,
    confirm_execution: bool,
) -> dict | None:
    if not chat.awaiting_confirmation or not chat.pending_action:
        return None

    pending = dict(chat.pending_action or {})

    if is_cancellation_text(text):
        chat.awaiting_confirmation = False
        chat.pending_action = None
        db.add(chat)
        db.commit()
        assistant = _save_message(
            db,
            chat=chat,
            role=MessageRole.assistant,
            content="Execucao cancelada. Se quiser, ajuste os parametros e me peca novamente.",
        )
        return {
            "intent": "cancel",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant),
            "user_message": _message_to_dict(user_message),
            "chat": _chat_to_dict(chat),
        }

    if not confirm_execution and not is_confirmation_text(text):
        # Check if the user is making a completely new request instead of confirming.
        # If so, clear the pending state and let the normal extraction flow handle it.
        new_extraction = extract_with_langgraph(text)
        if new_extraction.intent in ("search_leads", "market"):
            chat.awaiting_confirmation = False
            chat.pending_action = None
            db.add(chat)
            db.commit()
            return None  # Fall through to normal extraction in handle_chat

        assistant = _save_message(
            db,
            chat=chat,
            role=MessageRole.assistant,
            content="Confirma a execucao? Responda 'Sim' para iniciar ou 'Cancelar' para desistir.",
        )
        return {
            "intent": pending.get("action", "pending"),
            "requires_confirmation": True,
            "parsed_request": pending,
            "assistant_message": _message_to_dict(assistant),
            "user_message": _message_to_dict(user_message),
            "chat": _chat_to_dict(chat),
        }

    action = pending.get("action")
    if action == "search_leads":
        quantity = int(pending.get("quantity") or 5)
        assert_lead_quota(user, quantity)

        task = _create_task(
            db,
            user,
            chat,
            task_type=TaskType.scraping,
            prompt=pending.get("original_prompt") or text,
            parsed_payload=pending,
            requested_quantity=quantity,
        )

        async_job = run_scrape_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)

        chat.awaiting_confirmation = False
        chat.pending_action = None
        db.add(chat)
        db.commit()
        db.refresh(task)

        assistant = _save_message(
            db,
            chat=chat,
            role=MessageRole.assistant,
            content="Busca iniciada. Vou inserir apenas leads reais e ineditos no seu painel.",
            tool_calls=[{"tool": "search_businesses", "status": "started", "task_id": str(task.id)}],
        )
        return {
            "intent": "scrape",
            "requires_confirmation": False,
            "parsed_request": pending,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant),
            "user_message": _message_to_dict(user_message),
            "chat": _chat_to_dict(chat),
        }

    if action == "market":
        assert_external_query_quota(user, 1)
        task = _create_task(
            db,
            user,
            chat,
            task_type=TaskType.market_intelligence,
            prompt=pending.get("original_prompt") or text,
            parsed_payload=pending,
            requested_quantity=1,
        )

        async_job = run_market_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)

        chat.awaiting_confirmation = False
        chat.pending_action = None
        db.add(chat)
        db.commit()
        db.refresh(task)

        assistant = _save_message(
            db,
            chat=chat,
            role=MessageRole.assistant,
            content="Analise de mercado iniciada. Vou retornar o score e os sinais de oportunidade.",
            tool_calls=[{"tool": "market_analysis", "status": "started", "task_id": str(task.id)}],
        )
        return {
            "intent": "market",
            "requires_confirmation": False,
            "parsed_request": pending,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant),
            "user_message": _message_to_dict(user_message),
            "chat": _chat_to_dict(chat),
        }

    chat.awaiting_confirmation = False
    chat.pending_action = None
    db.add(chat)
    db.commit()
    assistant = _save_message(db, chat=chat, role=MessageRole.assistant, content="Acao pendente invalida. Tente novamente.")
    return {
        "intent": "assistant",
        "requires_confirmation": False,
        "assistant_message": _message_to_dict(assistant),
        "user_message": _message_to_dict(user_message),
        "chat": _chat_to_dict(chat),
    }


def handle_chat(db: Session, user: User, message: str, confirm_execution: bool, chat_id: str | None = None) -> dict:
    chat = _get_or_create_chat(db, user, chat_id)

    user_message = _save_message(db, chat=chat, role=MessageRole.user, content=message)
    _ensure_chat_title(db, chat, message)

    pending_result = _confirm_or_execute_pending(db, user, chat, user_message, message, confirm_execution)
    if pending_result is not None:
        return pending_result

    extraction = extract_with_langgraph(message)

    if extraction.intent == "search_leads":
        if extraction.missing_fields:
            missing_text = ", ".join(extraction.missing_fields)
            assistant = _save_message(
                db,
                chat=chat,
                role=MessageRole.assistant,
                content=f"Preciso de mais dados para buscar leads: {missing_text}.",
            )
            return {
                "intent": "clarify",
                "requires_confirmation": False,
                "assistant_message": _message_to_dict(assistant),
                "user_message": _message_to_dict(user_message),
                "chat": _chat_to_dict(chat),
            }

        quantity = max(1, min(int(extraction.quantity or 5), 100))
        parsed = {
            "action": "search_leads",
            "niche": extraction.niche or "negocios locais",
            "country": extraction.country or "Brasil",
            "city": extraction.city,
            "quantity": quantity,
            "original_prompt": message,
        }

        summary = (
            f"Resumo da busca: nicho={parsed['niche']}, pais={parsed['country']}, "
            f"cidade={parsed['city'] or 'Nacional'}, quantidade={parsed['quantity']}. Confirmar?"
        )

        chat.awaiting_confirmation = True
        chat.pending_action = parsed
        db.add(chat)
        db.commit()

        assistant = _save_message(
            db,
            chat=chat,
            role=MessageRole.assistant,
            content=summary,
            tool_calls=[{"tool": "search_businesses", "status": "awaiting_confirmation", "parsed": parsed}],
        )
        return {
            "intent": "scrape",
            "requires_confirmation": True,
            "parsed_request": parsed,
            "assistant_message": _message_to_dict(assistant),
            "user_message": _message_to_dict(user_message),
            "chat": _chat_to_dict(chat),
        }

    if extraction.intent == "market":
        parsed = {
            "action": "market",
            "niche": extraction.niche or "negocios locais",
            "country": extraction.country or "Brasil",
            "city": extraction.city,
            "original_prompt": message,
        }
        chat.awaiting_confirmation = True
        chat.pending_action = parsed
        db.add(chat)
        db.commit()

        assistant = _save_message(
            db,
            chat=chat,
            role=MessageRole.assistant,
            content=(
                f"Resumo da analise: nicho={parsed['niche']}, pais={parsed['country']}, "
                f"cidade={parsed['city'] or 'Nacional'}. Confirmar?"
            ),
            tool_calls=[{"tool": "market_analysis", "status": "awaiting_confirmation", "parsed": parsed}],
        )
        return {
            "intent": "market",
            "requires_confirmation": True,
            "parsed_request": parsed,
            "assistant_message": _message_to_dict(assistant),
            "user_message": _message_to_dict(user_message),
            "chat": _chat_to_dict(chat),
        }

    assistant = _save_message(
        db,
        chat=chat,
        role=MessageRole.assistant,
        content=extraction.response or "Posso buscar leads reais por nicho e regiao. Descreva seu pedido.",
    )

    return {
        "intent": "assistant",
        "requires_confirmation": False,
        "assistant_message": _message_to_dict(assistant),
        "user_message": _message_to_dict(user_message),
        "chat": _chat_to_dict(chat),
    }


def list_tasks(db: Session, user: User, limit: int = 20, chat_id: str | None = None) -> list[dict]:
    query = db.query(AITask).filter(AITask.user_id == user.id)
    if chat_id:
        query = query.filter(AITask.chat_id == _canonical_id(chat_id))

    rows = query.order_by(AITask.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return [_task_to_dict(item) for item in rows]


def get_task(db: Session, user: User, task_id: str) -> dict:
    parsed_task_id = _canonical_id(task_id)
    if not parsed_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task id")

    task = db.query(AITask).filter(AITask.id == parsed_task_id, AITask.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return _task_to_dict(task)


