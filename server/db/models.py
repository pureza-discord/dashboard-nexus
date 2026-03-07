import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db.base import Base


def utcnow() -> datetime:
    return datetime.utcnow()


def new_uuid() -> str:
    return str(uuid.uuid4())


def default_plan_reset_date() -> date:
    today = date.today()
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    return date(year, month, 1)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlanType(str, enum.Enum):
    free = "free"
    go = "go"
    pro = "pro"
    plus = "plus"
    ilimitado = "ilimitado"
    # Legacy aliases (mapped to new tiers in billing service)
    basic = "basic"
    enterprise = "enterprise"


class CreditTransactionType(str, enum.Enum):
    monthly_reset = "monthly_reset"
    purchase = "purchase"
    usage = "usage"
    refund = "refund"
    admin_adjustment = "admin_adjustment"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    trialing = "trialing"


class BillingCycle(str, enum.Enum):
    monthly = "monthly"
    annual = "annual"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class PaymentMethod(str, enum.Enum):
    pix = "pix"
    credit_card = "credit_card"


class LeadStatus(str, enum.Enum):
    novos = "novos"
    contatados = "contatados"
    proposta = "proposta"
    fechados = "fechados"
    perdidos = "perdidos"


class TaskType(str, enum.Enum):
    scraping = "scraping"
    market_intelligence = "market_intelligence"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class VerificationPurpose(str, enum.Enum):
    signup = "signup"
    login = "login"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    plan_type: Mapped[PlanType] = mapped_column(Enum(PlanType), default=PlanType.free)
    leads_limit_monthly: Mapped[int] = mapped_column(Integer, default=150)
    leads_used_current_month: Mapped[int] = mapped_column(Integer, default=0)
    external_queries_limit_monthly: Mapped[int] = mapped_column(Integer, default=5)
    external_queries_used_current_month: Mapped[int] = mapped_column(Integer, default=0)
    credits_balance: Mapped[int] = mapped_column(Integer, default=150)
    plan_reset_date: Mapped[date] = mapped_column(Date, default=default_plan_reset_date)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    leads: Mapped[list["Lead"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_tasks: Mapped[list["AITask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_messages: Mapped[list["AIMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    market_insights: Mapped[list["MarketInsight"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    verification_codes: Mapped[list["EmailVerificationCode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_lead_user_fingerprint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    empresa: Mapped[str] = mapped_column(String(255), index=True)
    telefone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    pais: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    nicho: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    origem: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.novos, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    chance_fechamento: Mapped[float] = mapped_column(Float, default=0.0)
    ticket_estimado: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    proximo_follow_up: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="leads")


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.queued, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    prompt: Mapped[str] = mapped_column(Text)
    parsed_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_quantity: Mapped[int] = mapped_column(Integer, default=0)
    completed_quantity: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="ai_tasks")
    messages: Mapped[list["AIMessage"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), index=True)
    content: Mapped[str] = mapped_column(Text)
    message_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="ai_messages")
    task: Mapped[AITask | None] = relationship(back_populates="messages")


class MarketInsight(Base):
    __tablename__ = "market_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nicho: Mapped[str] = mapped_column(String(180), index=True)
    cidade: Mapped[str] = mapped_column(String(120), index=True)
    pais: Mapped[str] = mapped_column(String(120), index=True)
    search_volume: Mapped[float] = mapped_column(Float, default=0.0)
    company_count: Mapped[int] = mapped_column(Integer, default=0)
    digital_presence_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_index: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_index: Mapped[float] = mapped_column(Float, default=0.0)
    market_score: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_potential: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    risk_level: Mapped[str] = mapped_column(String(40), default="medium")
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="market_insights")


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[VerificationPurpose] = mapped_column(Enum(VerificationPurpose), index=True)
    code_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="verification_codes")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_type: Mapped[PlanType] = mapped_column(Enum(PlanType), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.active, index=True
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(Enum(BillingCycle), default=BillingCycle.monthly)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    current_period_end: Mapped[datetime] = mapped_column(DateTime())
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    external_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="subscriptions")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[CreditTransactionType] = mapped_column(Enum(CreditTransactionType), index=True)
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    related_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="credit_transactions")


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending, index=True)
    amount_brl: Mapped[float] = mapped_column(Numeric(12, 2))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    pix_qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_qr_code_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

