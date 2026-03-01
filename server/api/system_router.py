from datetime import datetime, timezone

from fastapi import APIRouter

from server.core.settings import get_settings

router = APIRouter(prefix="/api", tags=["system"])


def _mask_secret(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://***@{host}"


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "ok": True,
        "service": settings.app_name,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {"url": _mask_secret(settings.database_url)},
        "redis": {"url": settings.redis_url},
        "scraper_mode": settings.scraper_mode,
    }
