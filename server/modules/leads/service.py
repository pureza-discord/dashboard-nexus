import csv
import hashlib
import io
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from server.db.models import Lead, LeadStatus, User


def _now_utc() -> datetime:
    return datetime.utcnow()


def _lead_status(value: str | None) -> LeadStatus | None:
    if not value or value == "todos":
        return None
    try:
        return LeadStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter") from exc


def _parse_id(raw_id: str) -> str:
    try:
        return str(uuid.UUID(raw_id))
    except Exception:
        raw = str(raw_id).strip()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lead id")
        return raw


def _lead_fingerprint(data: dict) -> str:
    base = "|".join(
        [
            str(data.get("empresa", "")).strip().lower(),
            str(data.get("email", "")).strip().lower(),
            str(data.get("telefone", "")).strip().lower(),
            str(data.get("cidade", "")).strip().lower(),
            str(data.get("pais", "")).strip().lower(),
        ]
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _compute_score(data: dict) -> int:
    score = 15
    if data.get("telefone"):
        score += 25
    if data.get("email"):
        score += 25
    if data.get("site"):
        score += 15
    if data.get("observacoes"):
        score += 10
    if data.get("cidade"):
        score += 5
    if data.get("pais"):
        score += 5
    return max(0, min(100, score))


def _decimal_to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def serialize_lead(lead: Lead) -> dict:
    return {
        "id": str(lead.id),
        "_id": str(lead.id),
        "user_id": str(lead.user_id),
        "empresa": lead.empresa,
        "telefone": lead.telefone,
        "email": lead.email,
        "site": lead.site,
        "cidade": lead.cidade,
        "pais": lead.pais,
        "nicho": lead.nicho,
        "origem": lead.origem,
        "status": lead.status.value,
        "_status": lead.status.value,
        "score": lead.score,
        "chance_fechamento": float(lead.chance_fechamento or 0),
        "ticket_estimado": _decimal_to_float(lead.ticket_estimado),
        "ultimo_contato": lead.ultimo_contato.isoformat() if lead.ultimo_contato else None,
        "proximo_follow_up": lead.proximo_follow_up.isoformat() if lead.proximo_follow_up else None,
        "observacoes": lead.observacoes,
        "extra_data": lead.extra_data or {},
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        "_created": lead.created_at.isoformat() if lead.created_at else None,
        "_updated": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def list_leads(
    db: Session,
    user: User,
    *,
    status_filter: str | None,
    cidade: str | None,
    pais: str | None,
    nicho: str | None,
    search: str | None,
    page: int,
    per_page: int,
    sort_by: str,
    sort_dir: str,
) -> dict:
    page = max(1, page)
    per_page = max(1, min(per_page, 200))

    query = db.query(Lead).filter(Lead.user_id == user.id)

    parsed_status = _lead_status(status_filter)
    if parsed_status:
        query = query.filter(Lead.status == parsed_status)

    if cidade:
        query = query.filter(Lead.cidade.ilike(f"%{cidade.strip()}%"))
    if pais:
        query = query.filter(Lead.pais.ilike(f"%{pais.strip()}%"))
    if nicho:
        query = query.filter(Lead.nicho.ilike(f"%{nicho.strip()}%"))

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Lead.empresa.ilike(term),
                Lead.telefone.ilike(term),
                Lead.email.ilike(term),
                Lead.site.ilike(term),
                Lead.cidade.ilike(term),
                Lead.pais.ilike(term),
                Lead.observacoes.ilike(term),
            )
        )

    total = query.count()

    sort_map = {
        "created_at": Lead.created_at,
        "updated_at": Lead.updated_at,
        "empresa": Lead.empresa,
        "cidade": Lead.cidade,
        "pais": Lead.pais,
        "status": Lead.status,
        "score": Lead.score,
        "ticket_estimado": Lead.ticket_estimado,
        "chance_fechamento": Lead.chance_fechamento,
    }
    sort_column = sort_map.get(sort_by, Lead.created_at)
    if sort_dir.lower() == "asc":
        order_by = sort_column.asc()
    else:
        order_by = desc(sort_column)

    leads = query.order_by(order_by).offset((page - 1) * per_page).limit(per_page).all()

    pages = max(1, (total + per_page - 1) // per_page)

    stats_rows = (
        db.query(Lead.status, func.count(Lead.id))
        .filter(Lead.user_id == user.id)
        .group_by(Lead.status)
        .all()
    )
    stats = {row[0].value: row[1] for row in stats_rows}
    stats["total"] = sum(stats.values())

    countries = [
        value
        for (value,) in (
            db.query(Lead.pais)
            .filter(and_(Lead.user_id == user.id, Lead.pais.isnot(None), Lead.pais != ""))
            .distinct()
            .order_by(Lead.pais.asc())
            .all()
        )
    ]

    return {
        "leads": [serialize_lead(item) for item in leads],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "stats": stats,
        "countries": countries,
    }


def get_lead(db: Session, user: User, lead_id: str) -> Lead:
    parsed_id = _parse_id(lead_id)
    lead = db.query(Lead).filter(Lead.id == parsed_id, Lead.user_id == user.id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


def update_lead(db: Session, user: User, lead_id: str, payload: dict) -> dict:
    lead = get_lead(db, user, lead_id)

    if payload.get("status"):
        lead.status = LeadStatus(payload["status"])
    if payload.get("ticket_estimado") is not None:
        lead.ticket_estimado = payload["ticket_estimado"]
    if payload.get("chance_fechamento") is not None:
        lead.chance_fechamento = payload["chance_fechamento"]
    if payload.get("proximo_follow_up") is not None:
        lead.proximo_follow_up = payload["proximo_follow_up"]
    if payload.get("ultimo_contato") is not None:
        lead.ultimo_contato = payload["ultimo_contato"]
    if payload.get("observacoes") is not None:
        lead.observacoes = payload["observacoes"]
    if payload.get("score") is not None:
        lead.score = payload["score"]

    lead.updated_at = _now_utc()
    db.add(lead)
    db.commit()
    db.refresh(lead)

    return serialize_lead(lead)


def delete_lead(db: Session, user: User, lead_id: str) -> None:
    lead = get_lead(db, user, lead_id)
    db.delete(lead)
    db.commit()


def bulk_update_status(db: Session, user: User, lead_ids: list[str], status: str) -> int:
    if not lead_ids:
        return 0

    parsed_ids = [_parse_id(item) for item in lead_ids]
    updated = (
        db.query(Lead)
        .filter(Lead.user_id == user.id, Lead.id.in_(parsed_ids))
        .update({Lead.status: LeadStatus(status), Lead.updated_at: _now_utc()}, synchronize_session=False)
    )
    db.commit()
    return int(updated)


def upsert_leads(db: Session, user: User, leads_payload: list[dict]) -> dict:
    if not leads_payload:
        return {"inserted": 0, "duplicates": 0, "total_received": 0}

    prepared: list[dict] = []
    fingerprints: list[str] = []
    for raw in leads_payload:
        empresa = str(raw.get("empresa") or raw.get("nome_empresa") or "").strip()
        if not empresa:
            continue

        item = {
            "empresa": empresa,
            "telefone": str(raw.get("telefone") or "").strip() or None,
            "email": str(raw.get("email") or "").strip().lower() or None,
            "site": str(raw.get("site") or "").strip() or None,
            "cidade": str(raw.get("cidade") or "").strip() or None,
            "pais": str(raw.get("pais") or "").strip() or None,
            "nicho": str(raw.get("nicho") or "").strip() or None,
            "origem": str(raw.get("origem") or "").strip() or "ai_scraper",
            "observacoes": str(raw.get("observacoes") or "").strip() or None,
            "ticket_estimado": raw.get("ticket_estimado"),
            "chance_fechamento": raw.get("chance_fechamento"),
            "score": raw.get("score"),
            "extra_data": raw,
        }

        fingerprint = _lead_fingerprint(item)
        item["fingerprint"] = fingerprint
        prepared.append(item)
        fingerprints.append(fingerprint)

    if not prepared:
        return {"inserted": 0, "duplicates": 0, "total_received": len(leads_payload)}

    existing_fingerprints = {
        value
        for (value,) in (
            db.query(Lead.fingerprint)
            .filter(Lead.user_id == user.id, Lead.fingerprint.in_(fingerprints))
            .all()
        )
    }

    inserted = 0
    duplicates = 0

    for item in prepared:
        if item["fingerprint"] in existing_fingerprints:
            duplicates += 1
            continue

        score = item["score"] if item["score"] is not None else _compute_score(item)
        chance = (
            float(item["chance_fechamento"])
            if item["chance_fechamento"] is not None
            else round(max(8.0, min(92.0, score * 0.78)), 1)
        )
        ticket = (
            float(item["ticket_estimado"])
            if item["ticket_estimado"] is not None
            else round(1200 + (score * 35), 2)
        )

        lead = Lead(
            user_id=user.id,
            fingerprint=item["fingerprint"],
            empresa=item["empresa"],
            telefone=item["telefone"],
            email=item["email"],
            site=item["site"],
            cidade=item["cidade"],
            pais=item["pais"],
            nicho=item["nicho"],
            origem=item["origem"],
            observacoes=item["observacoes"],
            score=int(score),
            chance_fechamento=float(chance),
            ticket_estimado=float(ticket),
            status=LeadStatus.novos,
            extra_data=item["extra_data"],
        )
        db.add(lead)
        existing_fingerprints.add(item["fingerprint"])
        inserted += 1

    db.commit()

    return {
        "inserted": inserted,
        "duplicates": duplicates,
        "total_received": len(leads_payload),
    }


def export_csv_content(db: Session, user: User) -> str:
    leads = db.query(Lead).filter(Lead.user_id == user.id).order_by(Lead.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "empresa",
            "telefone",
            "email",
            "site",
            "cidade",
            "pais",
            "nicho",
            "status",
            "score",
            "ticket_estimado",
            "chance_fechamento",
            "ultimo_contato",
            "proximo_follow_up",
            "observacoes",
            "created_at",
        ]
    )

    for lead in leads:
        writer.writerow(
            [
                str(lead.id),
                lead.empresa,
                lead.telefone or "",
                lead.email or "",
                lead.site or "",
                lead.cidade or "",
                lead.pais or "",
                lead.nicho or "",
                lead.status.value,
                lead.score,
                _decimal_to_float(lead.ticket_estimado),
                float(lead.chance_fechamento or 0),
                lead.ultimo_contato.isoformat() if lead.ultimo_contato else "",
                lead.proximo_follow_up.isoformat() if lead.proximo_follow_up else "",
                lead.observacoes or "",
                lead.created_at.isoformat() if lead.created_at else "",
            ]
        )

    return output.getvalue()

