import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_RELATIVE = "data/leads.db"
LEGACY_DB_RELATIVES = ("leads.db",)


def resolve_project_path(raw: str | None, fallback_relative: str) -> Path:
    value = (raw or fallback_relative).strip()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def resolve_db_path(
    *,
    explicit_db_path: str | None = None,
    config_db_path: str | None = None,
    fallback_relative: str = DEFAULT_DB_RELATIVE,
) -> tuple[str, str]:
    raw_env = os.getenv("DB_PATH", "").strip()
    raw = (explicit_db_path or "").strip() or raw_env or (config_db_path or "").strip()

    if raw:
        target = resolve_project_path(raw, fallback_relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        return str(target), "explicit"

    canonical = resolve_project_path(None, fallback_relative)
    if canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        return str(canonical), "canonical"

    for rel in LEGACY_DB_RELATIVES:
        legacy = (PROJECT_ROOT / rel).resolve()
        if legacy.exists():
            legacy.parent.mkdir(parents=True, exist_ok=True)
            return str(legacy), f"legacy:{rel}"

    canonical.parent.mkdir(parents=True, exist_ok=True)
    return str(canonical), "canonical-new"

