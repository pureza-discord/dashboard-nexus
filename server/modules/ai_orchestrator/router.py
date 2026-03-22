from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.ai_orchestrator.schemas import ChatRequest, ChatSessionResponse, MessageResponse
from server.modules.ai_orchestrator.service import delete_messages, get_task, handle_chat, list_messages, list_tasks, list_chat_sessions

router = APIRouter(prefix="/api/ai", tags=["ai_orchestrator"])


@router.post("/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return handle_chat(db, current_user, payload.message, payload.confirm_execution, session_id=payload.session_id)


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_chat_sessions(db, current_user)


@router.get("/chat/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_messages(db, current_user, session_id=session_id, limit=limit)}


@router.delete("/chat/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = delete_messages(db, current_user, session_id=session_id)
    return {"ok": True, "deleted": count}


@router.get("/messages")
def messages(
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_messages(db, current_user, limit=limit)}


@router.delete("/messages")
def clear_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = delete_messages(db, current_user)
    return {"ok": True, "deleted": count}


@router.get("/tasks")
def tasks(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_tasks(db, current_user, limit=limit)}


@router.get("/tasks/{task_id}")
def task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_task(db, current_user, task_id)
