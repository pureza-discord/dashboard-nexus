from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.billing.service import can_export_csv
from server.modules.leads.schemas import BulkInsertRequest, BulkStatusRequest, LeadUpdateRequest
from server.modules.leads.service import (
    bulk_update_status,
    delete_lead,
    export_csv_content,
    get_lead,
    list_leads,
    serialize_lead,
    update_lead,
    upsert_leads,
)

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("")
def read_leads(
    status_filter: str | None = Query(default="todos", alias="status"),
    cidade: str | None = Query(default=None),
    pais: str | None = Query(default=None),
    nicho: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_leads(
        db,
        current_user,
        status_filter=status_filter,
        cidade=cidade,
        pais=pais,
        nicho=nicho,
        search=search,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/{lead_id}")
def read_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = get_lead(db, current_user, lead_id)
    return serialize_lead(lead)


@router.patch("/{lead_id}")
def patch_lead(
    lead_id: str,
    payload: LeadUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_lead(db, current_user, lead_id, payload.model_dump(exclude_unset=True))


@router.post("/bulk/status")
def patch_bulk_status(
    payload: BulkStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = bulk_update_status(db, current_user, payload.lead_ids, payload.status)
    return {"ok": True, "updated": updated}


@router.delete("/{lead_id}")
def remove_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_lead(db, current_user, lead_id)
    return {"ok": True}


@router.post("/bulk/upsert")
def insert_leads(
    payload: BulkInsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = upsert_leads(db, current_user, [item.model_dump() for item in payload.leads])
    return {"ok": True, **result}


@router.get("/export/csv")
def export_leads_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_export_csv(current_user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="CSV export is available only for Pro and Enterprise plans",
        )

    csv_content = export_csv_content(db, current_user)
    headers = {"Content-Disposition": "attachment; filename=leads.csv"}
    return Response(content=csv_content, media_type="text/csv", headers=headers)
