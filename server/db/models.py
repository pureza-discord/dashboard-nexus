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
from sqlalchemy.dialects.postgresql import JSONB
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


JSONType = JSON().with_variant(JSONB, "postgresql")


class PlanType(str, enum.Enum):
    basic = "basic"
    pro = "pro"
    enterprise = "enterprise"


class LeadStatus(str, enum.Enum):
    novos = "novos"
    contatados = "contatados"
    proposta = "proposta"
    fechados = "fechados"
    perdidos = "perdidos"


class TaskType(str, enum.Enum):
    scraping = "scraping"
    market_intelligence = "market_intelligence"
    workana = "workana"
    services = "services"


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
    tool = "tool"


class VerificationPurpose(str, enum.Enum):
    signup = "signup"
    login = "login"
    password_reset = "password_reset"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    plan_type: Mapped[PlanType] = mapped_column(Enum(PlanType), default=PlanType.basic)
    leads_limit_monthly: Mapped[int] = mapped_column(Integer, default=300)
    leads_used_current_month: Mapped[int] = mapped_column(Integer, default=0)
    external_queries_limit_monthly: Mapped[int] = mapped_column(Integer, default=30)
    external_queries_used_current_month: Mapped[int] = mapped_column(Integer, default=0)
    credits_balance: Mapped[int] = mapped_column(Integer, default=0)
    plan_reset_date: Mapped[date] = mapped_column(Date, default=default_plan_reset_date)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    verification_tokens: Mapped[list["VerificationToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chats: Mapped[list["Chat"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_tasks: Mapped[list["AITask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    lead_history: Mapped[list["UserLeadHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    market_insights: Mapped[list["MarketInsight"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[VerificationPurpose] = mapped_column(Enum(VerificationPurpose), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="verification_tokens")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), default="Nova conversa")
    awaiting_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_action: Mapped[dict | None] = mapped_column(JSONType, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")
    tasks: Mapped[list["AITask"]] = relationship(back_populates="chat")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    chat_id: Mapped[str] = mapped_column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), index=True)
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list | dict | None] = mapped_column(JSONType, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)

    chat: Mapped[Chat] = relationship(back_populates="messages")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lead_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    niche: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    histories: Mapped[list["UserLeadHistory"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class UserLeadHistory(Base):
    __tablename__ = "user_lead_history"
    __table_args__ = (UniqueConstraint("user_id", "lead_hash", name="uq_user_lead_history_user_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    lead_hash: Mapped[str] = mapped_column(String(64), index=True)

    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.novos, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    chance_fechamento: Mapped[float] = mapped_column(Float, default=0.0)
    ticket_estimado: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    proximo_follow_up: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead_data: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="lead_history")
    lead: Mapped[Lead] = relationship(back_populates="histories")


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.queued, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    prompt: Mapped[str] = mapped_column(Text)
    parsed_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    requested_quantity: Mapped[int] = mapped_column(Integer, default=0)
    completed_quantity: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="ai_tasks")
    chat: Mapped[Chat | None] = relationship(back_populates="tasks")


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
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="market_insights")