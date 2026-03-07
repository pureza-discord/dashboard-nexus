from pydantic import BaseModel, Field


class SubscribeRequest(BaseModel):
    plan_type: str = Field(pattern=r"^(free|go|pro|plus|ilimitado)$")


class BuyCreditsRequest(BaseModel):
    amount: int = Field(description="Must be one of: 500, 2500, 10000")


class PlanPaymentRequest(BaseModel):
    plan_key: str = Field(pattern=r"^(go|pro|plus|ilimitado)$")
    billing_cycle: str = Field(default="monthly", pattern=r"^(monthly|annual)$")


class CreditsPaymentRequest(BaseModel):
    credits: int = Field(description="Credit pack size: 500, 2500, or 10000")


class AdminCreditAdjustment(BaseModel):
    user_id: str
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    description: str = Field(default="Admin adjustment", max_length=500)


class AdminPlanChange(BaseModel):
    user_id: str
    plan_type: str = Field(pattern=r"^(free|go|pro|plus|ilimitado)$")
