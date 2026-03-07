"""initial nexus leads schema with chats and user lead history

Revision ID: 20260305_1645
Revises:
Create Date: 2026-03-05 16:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260305_1645"
down_revision = None
branch_labels = None
depends_on = None


plan_type_enum = sa.Enum("basic", "pro", "enterprise", name="plantype")
lead_status_enum = sa.Enum("novos", "contatados", "proposta", "fechados", "perdidos", name="leadstatus")
task_type_enum = sa.Enum("scraping", "market_intelligence", "workana", "services", name="tasktype")
task_status_enum = sa.Enum("queued", "running", "completed", "failed", "cancelled", name="taskstatus")
message_role_enum = sa.Enum("user", "assistant", "system", "tool", name="messagerole")
verification_purpose_enum = sa.Enum("signup", "login", "password_reset", name="verificationpurpose")


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _ensure_column(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _ensure_index(table_name: str, index_name: str, columns: list[str], unique: bool = False) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=180), nullable=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("plan_type", plan_type_enum, nullable=False, server_default="basic"),
            sa.Column("leads_limit_monthly", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("leads_used_current_month", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("external_queries_limit_monthly", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("external_queries_used_current_month", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("credits_balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("plan_reset_date", sa.Date(), nullable=False),
            sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
            sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "verification_tokens" not in tables:
        op.create_table(
            "verification_tokens",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("purpose", verification_purpose_enum, nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_verification_tokens_user_id", "verification_tokens", ["user_id"])
        op.create_index("ix_verification_tokens_purpose", "verification_tokens", ["purpose"])
        op.create_index("ix_verification_tokens_token_hash", "verification_tokens", ["token_hash"])
        op.create_index("ix_verification_tokens_expires_at", "verification_tokens", ["expires_at"])

    if "chats" not in tables:
        op.create_table(
            "chats",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False, server_default="Nova conversa"),
            sa.Column("awaiting_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("pending_action", _json_type(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_chats_user_id", "chats", ["user_id"])

    if "messages" not in tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("chat_id", sa.String(length=36), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", message_role_enum, nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tool_calls", _json_type(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_messages_chat_id", "messages", ["chat_id"])
        op.create_index("ix_messages_role", "messages", ["role"])
        op.create_index("ix_messages_created_at", "messages", ["created_at"])

    if "leads" not in tables:
        op.create_table(
            "leads",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("lead_hash", sa.String(length=64), nullable=False),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=64), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("address", sa.String(length=512), nullable=True),
            sa.Column("website", sa.String(length=512), nullable=True),
            sa.Column("rating", sa.Float(), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("country", sa.String(length=120), nullable=True),
            sa.Column("niche", sa.String(length=180), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=True),
            sa.Column("raw_data", _json_type(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    else:
        _ensure_column("leads", sa.Column("lead_hash", sa.String(length=64), nullable=True))
        _ensure_column("leads", sa.Column("company_name", sa.String(length=255), nullable=True))
        _ensure_column("leads", sa.Column("phone", sa.String(length=64), nullable=True))
        _ensure_column("leads", sa.Column("address", sa.String(length=512), nullable=True))
        _ensure_column("leads", sa.Column("website", sa.String(length=512), nullable=True))
        _ensure_column("leads", sa.Column("rating", sa.Float(), nullable=True))
        _ensure_column("leads", sa.Column("city", sa.String(length=120), nullable=True))
        _ensure_column("leads", sa.Column("country", sa.String(length=120), nullable=True))
        _ensure_column("leads", sa.Column("niche", sa.String(length=180), nullable=True))
        _ensure_column("leads", sa.Column("source", sa.String(length=80), nullable=True))
        _ensure_column("leads", sa.Column("raw_data", _json_type(), nullable=True))

    _ensure_index("leads", "ix_leads_lead_hash", ["lead_hash"], unique=False)
    _ensure_index("leads", "ix_leads_company_name", ["company_name"], unique=False)
    _ensure_index("leads", "ix_leads_city", ["city"], unique=False)
    _ensure_index("leads", "ix_leads_country", ["country"], unique=False)
    _ensure_index("leads", "ix_leads_niche", ["niche"], unique=False)

    if "user_lead_history" not in tables:
        op.create_table(
            "user_lead_history",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("lead_id", sa.String(length=36), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("lead_hash", sa.String(length=64), nullable=False),
            sa.Column("status", lead_status_enum, nullable=False, server_default="novos"),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chance_fechamento", sa.Float(), nullable=False, server_default="0"),
            sa.Column("ticket_estimado", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("ultimo_contato", sa.DateTime(), nullable=True),
            sa.Column("proximo_follow_up", sa.DateTime(), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("lead_data", _json_type(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "lead_hash", name="uq_user_lead_history_user_hash"),
        )
        op.create_index("ix_user_lead_history_user_id", "user_lead_history", ["user_id"])
        op.create_index("ix_user_lead_history_lead_id", "user_lead_history", ["lead_id"])
        op.create_index("ix_user_lead_history_lead_hash", "user_lead_history", ["lead_hash"])
        op.create_index("ix_user_lead_history_status", "user_lead_history", ["status"])

    if "ai_tasks" not in tables:
        op.create_table(
            "ai_tasks",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chat_id", sa.String(length=36), sa.ForeignKey("chats.id", ondelete="SET NULL"), nullable=True),
            sa.Column("task_type", task_type_enum, nullable=False),
            sa.Column("status", task_status_enum, nullable=False, server_default="queued"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("parsed_payload", _json_type(), nullable=False),
            sa.Column("result_payload", _json_type(), nullable=False),
            sa.Column("requested_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("celery_task_id", sa.String(length=255), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ai_tasks_user_id", "ai_tasks", ["user_id"])
        op.create_index("ix_ai_tasks_task_type", "ai_tasks", ["task_type"])
        op.create_index("ix_ai_tasks_status", "ai_tasks", ["status"])
    else:
        _ensure_column("ai_tasks", sa.Column("chat_id", sa.String(length=36), nullable=True))

    if "market_insights" not in tables:
        op.create_table(
            "market_insights",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", sa.String(length=36), sa.ForeignKey("ai_tasks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("nicho", sa.String(length=180), nullable=False),
            sa.Column("cidade", sa.String(length=120), nullable=False),
            sa.Column("pais", sa.String(length=120), nullable=False),
            sa.Column("search_volume", sa.Float(), nullable=False, server_default="0"),
            sa.Column("company_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("digital_presence_ratio", sa.Float(), nullable=False, server_default="0"),
            sa.Column("saturation_index", sa.Float(), nullable=False, server_default="0"),
            sa.Column("opportunity_index", sa.Float(), nullable=False, server_default="0"),
            sa.Column("market_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("revenue_potential", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("risk_level", sa.String(length=40), nullable=False, server_default="medium"),
            sa.Column("raw_payload", _json_type(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_market_insights_user_id", "market_insights", ["user_id"])

    # Backfill lead snapshot table if old leads has user_id.
    inspector = inspect(bind)
    lead_cols = {c["name"] for c in inspector.get_columns("leads")} if "leads" in inspector.get_table_names() else set()
    if "user_id" in lead_cols and "empresa" in lead_cols:
        op.execute(
            sa.text(
                """
                UPDATE leads
                   SET company_name = COALESCE(company_name, empresa),
                       phone = COALESCE(phone, telefone),
                       website = COALESCE(website, site),
                       city = COALESCE(city, cidade),
                       country = COALESCE(country, pais),
                       niche = COALESCE(niche, nicho),
                       source = COALESCE(source, origem),
                       raw_data = COALESCE(raw_data, extra_data)
                 WHERE company_name IS NULL OR company_name = ''
                """
            )
        )


def downgrade() -> None:
    for table in [
        "market_insights",
        "user_lead_history",
        "messages",
        "verification_tokens",
        "chats",
    ]:
        bind = op.get_bind()
        if table in inspect(bind).get_table_names():
            op.drop_table(table)
