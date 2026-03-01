from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.auth.service import serialize_user
from server.modules.users.schemas import UpdatePlanRequest, UpdateProfileRequest
from server.modules.users.service import update_plan, update_profile

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@router.patch("/me")
def patch_me(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_profile(db, current_user, payload.full_name)


@router.patch("/me/plan")
def patch_plan(
    payload: UpdatePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_plan(db, current_user, payload.plan_type)
