from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    full_name: str | None = Field(default=None, max_length=180)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class VerifyEmailCodeRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=4, max_length=12)


class ResendCodeRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class TokenPayload(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
