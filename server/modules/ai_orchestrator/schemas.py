from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    chat_id: str | None = None
    confirm_execution: bool = False


class CreateChatRequest(BaseModel):
    title: str | None = Field(default=None, max_length=240)


class TaskStatusResponse(BaseModel):
    id: str
    chat_id: str | None = None
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
    chat_id: str
    role: str
    content: str
    tool_calls: list | dict | None = None
    created_at: str | None = None
