from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.market_intelligence_service.service import recent_reports

router = APIRouter(prefix="/api/market", tags=["market_intelligence"])


@router.get("/reports")
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": recent_reports(db, current_user, limit=limit)}
