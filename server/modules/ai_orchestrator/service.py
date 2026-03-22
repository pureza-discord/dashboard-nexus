import logging
import re
import uuid

from fastapi import HTTPException, status  # type: ignore
from sqlalchemy.orm import Session  # type: ignore

from server.db.models import AIMessage, AITask, MessageRole, TaskStatus, TaskType, User  # type: ignore
from server.modules.billing.service import (  # type: ignore
    assert_external_query_quota,
    assert_lead_quota,
    consume_ai_message,
    get_policy,
)
from server.workers.tasks import run_market_task, run_scrape_task  # type: ignore

logger = logging.getLogger("ai_orchestrator")

# ---------------------------------------------------------------------------
# Valid scraping sources
# ---------------------------------------------------------------------------

VALID_SOURCES = {"google_maps", "google_search", "workana", "linkedin", "facebook", "procura_servico"}

# ---------------------------------------------------------------------------
# Deterministic command patterns (Portuguese + English)
# ---------------------------------------------------------------------------

# Search patterns — ordered most-specific first
SEARCH_PATTERNS = [
    # "buscar {qty} {niche} em {city}, {country}" — must be first (qty before niche)
    re.compile(
        r"(?:buscar|procurar|pesquisar|search|find)\s+(?P<qty>\d+)\s+"
        r"(?P<nicho>.+?)\s+(?:em|in)\s+(?P<cidade>.+?),\s*(?P<pais>.+?)\s*$",
        re.IGNORECASE,
    ),
    # "buscar {qty} {niche} em {country}" — qty before niche, no city
    re.compile(
        r"(?:buscar|procurar|pesquisar|search|find)\s+(?P<qty>\d+)\s+"
        r"(?P<nicho>.+?)\s+(?:em|in)\s+(?P<pais>[^,]+?)\s*$",
        re.IGNORECASE,
    ),
    # "buscar leads de {niche} em {city}, {country} [quantidade:N] [fonte:X]"
    re.compile(
        r"(?:buscar|procurar|pesquisar|search|find)\s+(?:leads?\s+)?(?:de\s+|for\s+)?"
        r"(?P<nicho>.+?)\s+(?:em|in)\s+(?P<cidade>.+?),\s*(?P<pais>.+?)"
        r"(?:\s+(?:quantidade|qty|qtd)\s*[:=]?\s*(?P<qty>\d+))?"
        r"(?:\s+(?:fonte|source)\s*[:=]?\s*(?P<fonte>\w+))?\s*$",
        re.IGNORECASE,
    ),
    # "buscar leads de {niche} em {country}" (no city — national scope)
    re.compile(
        r"(?:buscar|procurar|pesquisar|search|find)\s+(?:leads?\s+)?(?:de\s+|for\s+)?"
        r"(?P<nicho>.+?)\s+(?:em|in)\s+(?P<pais>[^,]+?)"
        r"(?:\s+(?:quantidade|qty|qtd)\s*[:=]?\s*(?P<qty>\d+))?"
        r"(?:\s+(?:fonte|source)\s*[:=]?\s*(?P<fonte>\w+))?\s*$",
        re.IGNORECASE,
    ),
]

# Market analysis patterns
MARKET_PATTERNS = [
    # "analisar mercado de {niche} em {city}, {country}"
    re.compile(
        r"(?:analisar|analise|analyze|analysis|mercado|market)\s+(?:mercado\s+)?"
        r"(?:de\s+|for\s+)?(?P<nicho>.+?)\s+(?:em|in)\s+(?P<cidade>.+?),\s*(?P<pais>.+?)\s*$",
        re.IGNORECASE,
    ),
    # "analisar mercado de {niche} em {country}" (no city)
    re.compile(
        r"(?:analisar|analise|analyze|analysis|mercado|market)\s+(?:mercado\s+)?"
        r"(?:de\s+|for\s+)?(?P<nicho>.+?)\s+(?:em|in)\s+(?P<pais>[^,]+?)\s*$",
        re.IGNORECASE,
    ),
]

HELP_KEYWORDS = {"ajuda", "help", "/help", "/ajuda"}
CREDITS_KEYWORDS = {"creditos", "créditos", "credits", "/credits", "/creditos"}

HELP_TEXT = (
    "Comandos disponíveis:\n\n"
    "Buscar leads:\n"
    "  buscar leads de [nicho] em [cidade], [país]\n"
    "  buscar [quantidade] [nicho] em [cidade], [país]\n"
    "  buscar leads de [nicho] em [país]  (escopo nacional)\n"
    "  Opções: quantidade:N  fonte:google_maps|workana|linkedin|facebook|procura_servico\n\n"
    "Análise de mercado:\n"
    "  analisar mercado de [nicho] em [cidade], [país]\n\n"
    "Outros:\n"
    "  ajuda / help — Esta mensagem\n"
    "  creditos / credits — Seu saldo de créditos\n"
    "  /clear — Limpar chat\n\n"
    "Exemplos:\n"
    "  buscar leads de restaurantes em São Paulo, Brasil\n"
    "  search leads for dental clinics in Toronto, Canada\n"
    "  buscar 200 clínicas em Lisboa, Portugal\n"
    "  analisar mercado de tech em Porto, Portugal\n"
    "  buscar leads de contadores em Brasil fonte:workana"
)


# ---------------------------------------------------------------------------
# Command parser
# ---------------------------------------------------------------------------

def _parse_command(text: str) -> dict:
    """Parse user input into a structured command dict."""
    stripped = text.strip()
    lower = stripped.lower()

    if lower in HELP_KEYWORDS:
        return {"intent": "help"}

    if lower in CREDITS_KEYWORDS:
        return {"intent": "credits"}

    # Try search patterns
    for pattern in SEARCH_PATTERNS:
        m = pattern.match(stripped)
        if m:
            groups = m.groupdict()
            nicho = (groups.get("nicho") or "").strip()
            pais = (groups.get("pais") or "").strip()
            cidade = (groups.get("cidade") or "").strip() or None
            raw_qty = groups.get("qty")
            fonte = (groups.get("fonte") or "").strip().lower()

            if not nicho or not pais:
                continue

            qty = _coerce_quantity(raw_qty)
            source = fonte if fonte in VALID_SOURCES else "google_maps"

            return {
                "intent": "scrape",
                "nicho": nicho,
                "cidade": cidade,
                "pais": pais,
                "quantidade": qty,
                "source": source,
            }

    # Try market patterns
    for pattern in MARKET_PATTERNS:
        m = pattern.match(stripped)
        if m:
            groups = m.groupdict()
            nicho = (groups.get("nicho") or "").strip()
            pais = (groups.get("pais") or "").strip()
            cidade = (groups.get("cidade") or "").strip() or None

            if not nicho or not pais:
                continue

            return {
                "intent": "market",
                "nicho": nicho,
                "cidade": cidade,
                "pais": pais,
            }

    return {"intent": "unknown"}


# ---------------------------------------------------------------------------
# Helpers (unchanged)
# ---------------------------------------------------------------------------

def _canonical_id(raw: str) -> str:
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(raw).strip()


def _message_to_dict(message: AIMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role.value,
        "content": message.content,
        "task_id": str(message.task_id) if message.task_id else None,
        "session_id": str(message.session_id) if message.session_id else None,
        "metadata": message.message_metadata or {},
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _task_to_dict(task: AITask) -> dict:
    return {
        "id": str(task.id),
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


def _save_message(
    db: Session,
    *,
    user: User,
    role: MessageRole,
    content: str,
    task_id: str | None = None,
    session_id: str | None = None,
    metadata: dict | None = None,
) -> AIMessage:
    row = AIMessage(
        user_id=user.id,
        task_id=task_id,
        session_id=session_id,
        role=role,
        content=content,
        message_metadata=metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _create_task(
    db: Session,
    user: User,
    *,
    task_type: TaskType,
    prompt: str,
    parsed_payload: dict,
    requested_quantity: int,
) -> AITask:
    task = AITask(
        user_id=user.id,
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


def _coerce_quantity(raw_quantity: int | float | str | None) -> int:
    try:
        qty = int(raw_quantity or 50)
    except Exception:
        qty = 50
    return max(1, min(qty, 1000))


# ---------------------------------------------------------------------------
# Main chat handler
# ---------------------------------------------------------------------------

def handle_chat(db: Session, user: User, message: str, confirm_execution: bool, session_id: str | None = None) -> dict:
    # /clear handling
    if str(message or "").strip().lower() == "/clear":
        deleted = delete_messages(db, user, session_id=session_id)
        return {
            "intent": "clear",
            "requires_confirmation": False,
            "deleted": deleted,
            "assistant_message": None,
            "user_message": None,
        }

    user_message = _save_message(db, user=user, role=MessageRole.user, content=message, session_id=session_id)

    # Charge credits for the message
    try:
        consume_ai_message(db, user)
    except HTTPException:
        reply = (
            "Seus créditos acabaram. Para continuar usando o sistema, "
            "compre mais créditos ou faça upgrade do seu plano."
        )
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=reply, session_id=session_id,
            metadata={"intent": "credits_exhausted", "requires_confirmation": False},
        )
        return {
            "intent": "credits_exhausted",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    parsed = _parse_command(message)

    # -- Help --
    if parsed["intent"] == "help":
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=HELP_TEXT, session_id=session_id,
            metadata={"intent": "help", "requires_confirmation": False},
        )
        return {
            "intent": "help",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # -- Credits --
    if parsed["intent"] == "credits":
        policy = get_policy(user.plan_type)
        if policy.monthly_credits is None:
            credit_info = f"Plano: {policy.display_name} (créditos ilimitados)."
        else:
            credit_info = (
                f"Plano: {policy.display_name}.\n"
                f"Créditos disponíveis: {user.credits_balance}/{policy.monthly_credits}."
            )
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=credit_info, session_id=session_id,
            metadata={"intent": "credits", "requires_confirmation": False},
        )
        return {
            "intent": "credits",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # -- Scrape --
    if parsed["intent"] == "scrape":
        nicho = parsed["nicho"]
        pais = parsed["pais"]
        cidade = parsed.get("cidade")
        quantidade = parsed["quantidade"]
        source = parsed.get("source", "google_maps")

        logger.info(
            "[CHAT] Intent: scrape | Nicho: %s | Country: %s | City: %s | Qty: %d | Source: %s",
            nicho, pais, cidade, quantidade, source,
        )

        scrape_parsed = {
            "nicho": nicho,
            "cidade": cidade,
            "pais": pais,
            "quantidade": quantidade,
            "scope": "nacional" if cidade is None else "cidade",
            "source": source,
        }

        assert_lead_quota(user, quantidade)

        if not confirm_execution:
            city_label = cidade or "Nacional"
            confirm_text = (
                f"Confirme a busca:\n"
                f"- Nicho: {nicho}\n"
                f"- Cidade: {city_label}\n"
                f"- País: {pais}\n"
                f"- Quantidade: {quantidade}\n"
                f"- Fonte: {source}"
            )
            assistant_message = _save_message(
                db, user=user, role=MessageRole.assistant, content=confirm_text, session_id=session_id,
                metadata={"intent": "scrape", "requires_confirmation": True, "parsed": scrape_parsed},
            )
            return {
                "intent": "scrape",
                "requires_confirmation": True,
                "parsed_request": scrape_parsed,
                "assistant_message": _message_to_dict(assistant_message),
                "user_message": _message_to_dict(user_message),
            }

        # Execute scrape
        task = _create_task(
            db, user, task_type=TaskType.scraping, prompt=message,
            parsed_payload=scrape_parsed, requested_quantity=quantidade,
        )
        async_job = run_scrape_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info(
            "[CHAT] Intent: scrape | Task: %s | Nicho: %s | Country: %s | City: %s | Qty: %d | Status: executing",
            task.id, nicho, pais, cidade, quantidade,
        )

        exec_text = (
            f"Busca iniciada! Procurando {quantidade} leads de '{nicho}' "
            f"em {cidade or 'escopo nacional'}, {pais}. "
            f"Acompanhe o progresso acima."
        )
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=exec_text,
            task_id=task.id, session_id=session_id,
            metadata={"intent": "scrape", "requires_confirmation": False, "task_id": str(task.id)},
        )
        return {
            "intent": "scrape",
            "requires_confirmation": False,
            "parsed_request": scrape_parsed,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # -- Market analysis --
    if parsed["intent"] == "market":
        nicho = parsed["nicho"]
        pais = parsed["pais"]
        cidade = parsed.get("cidade")

        logger.info(
            "[CHAT] Intent: market | Nicho: %s | Country: %s | City: %s",
            nicho, pais, cidade,
        )

        market_parsed = {
            "nicho": nicho,
            "cidade": cidade or pais,
            "pais": pais,
        }

        assert_external_query_quota(user, 1)

        if not confirm_execution:
            city_label = cidade or "Nacional"
            confirm_text = (
                f"Confirme a análise de mercado:\n"
                f"- Nicho: {nicho}\n"
                f"- Cidade: {city_label}\n"
                f"- País: {pais}"
            )
            assistant_message = _save_message(
                db, user=user, role=MessageRole.assistant, content=confirm_text, session_id=session_id,
                metadata={"intent": "market", "requires_confirmation": True, "parsed": market_parsed},
            )
            return {
                "intent": "market",
                "requires_confirmation": True,
                "parsed_request": market_parsed,
                "assistant_message": _message_to_dict(assistant_message),
                "user_message": _message_to_dict(user_message),
            }

        # Execute market analysis
        task = _create_task(
            db, user, task_type=TaskType.market_intelligence, prompt=message,
            parsed_payload=market_parsed, requested_quantity=1,
        )
        async_job = run_market_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info(
            "[CHAT] Intent: market | Task: %s | Nicho: %s | Country: %s | City: %s | Status: executing",
            task.id, nicho, pais, cidade,
        )

        exec_text = (
            f"Análise de mercado iniciada para '{nicho}' em {cidade or 'escopo nacional'}, {pais}. "
            f"Retornarei scores de oportunidade e risco baseados em dados reais."
        )
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=exec_text,
            task_id=task.id, session_id=session_id,
            metadata={"intent": "market", "task_id": str(task.id)},
        )
        return {
            "intent": "market",
            "requires_confirmation": False,
            "parsed_request": market_parsed,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # -- Unknown command --
    reply = (
        "Não entendi o comando. Tente:\n\n"
        "  buscar leads de [nicho] em [cidade], [país]\n"
        "  analisar mercado de [nicho] em [cidade], [país]\n"
        "  ajuda — lista completa de comandos\n"
        "  creditos — ver saldo"
    )
    logger.info("[CHAT] Intent: unknown | Message: %s", message[:100])
    assistant_message = _save_message(
        db, user=user, role=MessageRole.assistant, content=reply, session_id=session_id,
        metadata={"intent": "unknown", "requires_confirmation": False},
    )
    return {
        "intent": "unknown",
        "requires_confirmation": False,
        "assistant_message": _message_to_dict(assistant_message),
        "user_message": _message_to_dict(user_message),
    }


# ---------------------------------------------------------------------------
# Query functions (unchanged)
# ---------------------------------------------------------------------------

def list_messages(db: Session, user: User, session_id: str | None = None, limit: int = 50) -> list[dict]:
    query = db.query(AIMessage).filter(AIMessage.user_id == user.id)
    if session_id:
        query = query.filter(AIMessage.session_id == session_id)

    rows = (
        query
        .order_by(AIMessage.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_message_to_dict(item) for item in reversed(rows)]


def list_tasks(db: Session, user: User, limit: int = 20) -> list[dict]:
    rows = (
        db.query(AITask)
        .filter(AITask.user_id == user.id)
        .order_by(AITask.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [_task_to_dict(item) for item in rows]


def delete_messages(db: Session, user: User, session_id: str | None = None) -> int:
    query = db.query(AIMessage).filter(AIMessage.user_id == user.id)
    if session_id:
        query = query.filter(AIMessage.session_id == session_id)

    deleted = query.delete(synchronize_session=False)
    db.commit()
    return int(deleted)

def list_chat_sessions(db: Session, user: User) -> list[dict]:
    from sqlalchemy import func

    rows = (
        db.query(
            AIMessage.session_id,
            func.max(AIMessage.created_at).label("last_activity"),
            func.count(AIMessage.id).label("count")
        )
        .filter(AIMessage.user_id == user.id)
        .filter(AIMessage.session_id.isnot(None))
        .group_by(AIMessage.session_id)
        .order_by(func.max(AIMessage.created_at).desc())
        .limit(30)
        .all()
    )

    sessions = []
    for sid, last_date, count in rows:
        first_msg = (
            db.query(AIMessage)
            .filter(AIMessage.session_id == sid, AIMessage.role == MessageRole.user)
            .order_by(AIMessage.created_at.asc())
            .first()
        )
        title = first_msg.content[:40] + "..." if first_msg and first_msg.content else "Novo Chat"
        sessions.append({
            "session_id": sid,
            "title": title,
            "last_message_at": last_date.isoformat() if last_date else None,
            "message_count": count
        })
    return sessions


def get_task(db: Session, user: User, task_id: str) -> dict:
    parsed_task_id = _canonical_id(task_id)
    if not parsed_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task id")

    task = db.query(AITask).filter(AITask.id == parsed_task_id, AITask.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return _task_to_dict(task)
