import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _split_csv(raw: str | None, fallback: list[str]) -> list[str]:
    if not raw:
        return fallback
    values = [item.strip() for item in raw.split(",")]
    cleaned = [item for item in values if item]
    return cleaned or fallback


@dataclass(slots=True)
class Settings:
    app_name: str
    environment: str
    api_host: str
    api_port: int
    database_url: str
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    celery_task_always_eager: bool
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    cors_origins: list[str]
    cors_allow_credentials: bool
    scraper_mode: str
    openai_api_key: str | None
    enable_external_data: bool
    trends_geo_default: str
    log_level: str
    frontend_dist: str
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from_email: str | None
    smtp_use_tls: bool
    email_code_ttl_minutes: int
    auto_bootstrap_admin: bool
    bootstrap_admin_email: str
    bootstrap_admin_password: str
    openai_model: str
    asaas_api_base_url: str
    asaas_api_key: str | None
    asaas_webhook_token: str | None
    plan_price_basic_brl: float
    plan_price_pro_brl: float
    plan_price_enterprise_brl: float
    credit_price_per_unit_brl: float


def _default_database_url(environment: str) -> str:
    legacy_db_path = os.getenv("DB_PATH", "").strip()
    if legacy_db_path:
        return f"sqlite:///{Path(legacy_db_path).as_posix()}"
    if environment == "production":
        return "postgresql+psycopg://postgres:postgres@localhost:5432/nexus_leads"
    return f"sqlite:///{(PROJECT_ROOT / 'data' / 'dev.db').as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower() or "development"

    default_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip() or os.getenv("DASHBOARD_SECRET", "").strip()
    if not jwt_secret:
        if environment == "production":
            raise RuntimeError("JWT_SECRET_KEY is required in production.")
        jwt_secret = secrets.token_urlsafe(48)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip() or "redis://localhost:6379/0"
    celery_task_always_eager = _env_bool("CELERY_TASK_ALWAYS_EAGER", environment != "production")
    celery_broker_env = os.getenv("CELERY_BROKER_URL", "").strip()
    celery_backend_env = os.getenv("CELERY_RESULT_BACKEND", "").strip()

    celery_broker_url = celery_broker_env or redis_url
    celery_result_backend = celery_backend_env or redis_url.replace("/0", "/1")
    if celery_task_always_eager:
        celery_broker_url = celery_broker_env or "memory://"
        celery_result_backend = celery_backend_env or "cache+memory://"

    raw_db = os.getenv("DATABASE_URL", "").strip()
    database_url = raw_db or _default_database_url(environment)

    return Settings(
        app_name=os.getenv("APP_NAME", "Nexus Leads SaaS API").strip() or "Nexus Leads SaaS API",
        environment=environment,
        api_host=os.getenv("API_HOST", "0.0.0.0").strip() or "0.0.0.0",
        api_port=_env_int("API_PORT", 8000),
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=celery_broker_url,
        celery_result_backend=celery_result_backend,
        celery_task_always_eager=celery_task_always_eager,
        jwt_secret_key=jwt_secret,
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256").strip() or "HS256",
        access_token_expire_minutes=_env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24),
        cors_origins=_split_csv(os.getenv("CORS_ORIGINS"), default_origins),
        cors_allow_credentials=_env_bool("CORS_ALLOW_CREDENTIALS", True),
        scraper_mode=os.getenv("SCRAPER_MODE", "mock").strip().lower() or "mock",
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        enable_external_data=_env_bool("ENABLE_EXTERNAL_DATA", True),
        trends_geo_default=os.getenv("TRENDS_GEO_DEFAULT", "BR").strip().upper() or "BR",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        frontend_dist=str((PROJECT_ROOT / os.getenv("FRONTEND_DIST", "frontend/dist")).resolve()),
        smtp_host=os.getenv("SMTP_HOST", "").strip() or None,
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_user=os.getenv("SMTP_USER", "").strip() or None,
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip() or None,
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "").strip() or None,
        smtp_use_tls=_env_bool("SMTP_USE_TLS", True),
        email_code_ttl_minutes=max(1, _env_int("EMAIL_CODE_TTL_MINUTES", 5)),
        auto_bootstrap_admin=_env_bool("AUTO_BOOTSTRAP_ADMIN", True),
        bootstrap_admin_email=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@nexus.local").strip().lower() or "admin@nexus.local",
        bootstrap_admin_password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123").strip() or "admin123",
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
        asaas_api_base_url=os.getenv("ASAAS_API_BASE_URL", "https://api.asaas.com/v3").strip()
        or "https://api.asaas.com/v3",
        asaas_api_key=os.getenv("ASAAS_API_KEY", "").strip() or None,
        asaas_webhook_token=os.getenv("ASAAS_WEBHOOK_TOKEN", "").strip() or None,
        plan_price_basic_brl=_env_float("PLAN_PRICE_BASIC_BRL", 79.0),
        plan_price_pro_brl=_env_float("PLAN_PRICE_PRO_BRL", 199.0),
        plan_price_enterprise_brl=_env_float("PLAN_PRICE_ENTERPRISE_BRL", 799.0),
        credit_price_per_unit_brl=_env_float("CREDIT_PRICE_PER_UNIT_BRL", 1.0),
    )
