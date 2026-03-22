from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    confirm_execution: bool = False
    session_id: str | None = None


class TaskStatusResponse(BaseModel):
    id: str
    task_type: str
    status: str
    progress: int
    requested_quantity: int
    completed_quantity: int
    prompt: str
    parsed_payload: dict
    result_payload: dict
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    task_id: str | None = None
    session_id: str | None = None
    metadata: dict
    created_at: str | None = None

class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    last_message_at: str | None = None
    message_count: int
