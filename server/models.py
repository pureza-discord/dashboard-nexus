from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class MarkRequest(BaseModel):
    ids: list[int]
    status: str = Field(pattern=r"^(novo|contatado|fechado|ignorado)$")


class DeleteRequest(BaseModel):
    ids: list[int]


class ChangePasswordRequest(BaseModel):
    current: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=200)
