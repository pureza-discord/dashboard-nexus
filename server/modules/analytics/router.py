from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.analytics.service import get_overview, quick_metrics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_overview(db, current_user)


@router.get("")
def legacy_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Backward-compatible endpoint used by existing dashboard hooks.
    return get_overview(db, current_user)


@router.get("/quick")
def quick(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return quick_metrics(db, current_user)
