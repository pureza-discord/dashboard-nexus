from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.ai_orchestrator.schemas import ChatRequest
from server.modules.ai_orchestrator.service import get_task, handle_chat, list_messages, list_tasks

router = APIRouter(prefix="/api/ai", tags=["ai_orchestrator"])


@router.post("/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return handle_chat(db, current_user, payload.message, payload.confirm_execution)


@router.get("/messages")
def messages(
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": list_messages(db, current_user, limit=limit)}


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
