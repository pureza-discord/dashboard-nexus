from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.ai_orchestrator.schemas import ChatRequest, CreateChatRequest
from server.modules.ai_orchestrator.service import (
    clear_messages,
    create_chat,
    get_task,
    handle_chat,
    list_chats,
    list_messages,
    list_tasks,
)

router = APIRouter(prefix="/api/ai", tags=["ai_orchestrator"])


@router.post("/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return handle_chat(db, current_user, payload.message, payload.confirm_execution, payload.chat_id)


@router.get("/chats")
def chats(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_chats(db, current_user, limit=limit)}


@router.post("/chats")
def create_chat_endpoint(
    payload: CreateChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_chat(db, current_user, payload.title)


@router.get("/chats/{chat_id}/messages")
def messages_by_chat(
    chat_id: str,
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_messages(db, current_user, limit=limit, chat_id=chat_id)}


@router.delete("/chats/{chat_id}/messages")
def clear_messages_by_chat(
    chat_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = clear_messages(db, current_user, chat_id=chat_id)
    return {"ok": True, "deleted": deleted}


# Legacy endpoints kept for compatibility with old frontend calls.
@router.get("/messages")
def messages(
    limit: int = Query(default=60, ge=1, le=200),
    chat_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_messages(db, current_user, limit=limit, chat_id=chat_id)}


@router.delete("/messages")
def clear_messages_legacy(
    chat_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = clear_messages(db, current_user, chat_id=chat_id)
    return {"ok": True, "deleted": deleted}


@router.get("/tasks")
def tasks(
    limit: int = Query(default=20, ge=1, le=100),
    chat_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_tasks(db, current_user, limit=limit, chat_id=chat_id)}


@router.get("/tasks/{task_id}")
def task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_task(db, current_user, task_id)
