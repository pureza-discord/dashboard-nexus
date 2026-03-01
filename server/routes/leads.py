from fastapi import APIRouter, Depends, HTTPException

from server.middleware.auth import verify_token
from server.models import MarkRequest, DeleteRequest
from server.services import leads_service

router = APIRouter(prefix="/api", tags=["leads"])


@router.get("/leads")
async def list_leads(
    status: str = "todos",
    pais: str = "todos",
    cidade: str = "",
    search: str = "",
    created_from: str = "",
    created_to: str = "",
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "id",
    sort_dir: str = "desc",
    _user: str = Depends(verify_token),
):
    result = leads_service.get_leads(
        status=status, pais=pais, cidade=cidade, search=search,
        created_from=created_from, created_to=created_to,
        page=page, per_page=per_page,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    result["stats"] = leads_service.get_stats()
    result["countries"] = leads_service.get_countries()
    return result


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: int, _user: str = Depends(verify_token)):
    lead = leads_service.get_lead_detail(lead_id)
    if not lead:
        raise HTTPException(404, "Lead nao encontrado")
    return lead


@router.post("/leads/mark")
async def mark(req: MarkRequest, _user: str = Depends(verify_token)):
    updated = leads_service.mark_leads(req.ids, req.status)
    return {"ok": True, "updated": updated}


@router.post("/leads/delete")
async def delete(req: DeleteRequest, _user: str = Depends(verify_token)):
    deleted = leads_service.delete_leads(req.ids)
    return {"ok": True, "deleted": deleted}


@router.post("/leads/delete-by-status")
async def delete_by_status(req: MarkRequest, _user: str = Depends(verify_token)):
    deleted = leads_service.delete_by_status(req.status)
    return {"ok": True, "deleted": deleted}
