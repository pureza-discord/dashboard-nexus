from pydantic import BaseModel, Field


class SubscribeRequest(BaseModel):
    plan_type: str = Field(pattern=r"^(basic|pro|enterprise)$")


class BuyCreditsRequest(BaseModel):
    amount: int = Field(ge=1, le=100000)
