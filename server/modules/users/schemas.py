from pydantic import BaseModel, Field


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=180)


class UpdatePlanRequest(BaseModel):
    plan_type: str = Field(pattern=r"^(basic|pro|enterprise)$")
