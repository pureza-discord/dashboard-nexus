from datetime import datetime, timezone

from fastapi import APIRouter

from server.core.settings import get_settings

router = APIRouter(prefix="/api", tags=["system-legacy"])


@router.get("/health-legacy")
async def health_legacy():
    settings = get_settings()
    return {
        "ok": True,
        "service": settings.app_name,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {"url": settings.database_url},
        "redis": {"url": settings.redis_url},
    }
