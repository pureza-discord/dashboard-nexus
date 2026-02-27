from fastapi import APIRouter, Depends

from server.middleware.auth import verify_token
from server.services import analytics_service

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics")
async def analytics(_user: str = Depends(verify_token)):
    return analytics_service.get_analytics()
