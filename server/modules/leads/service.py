from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from server.db.models import Lead, LeadStatus, User, UserLeadHistory


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


def _lead_hash(company_name: str, city: str | None, phone: str | None) -> str:
    base = f"{(company_name or '').strip().lower()}|{(city or '').strip().lower()}|{(phone or '').strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _compute_score(phone: str | None, email: str | None, website: str | None, address: str | None) -> int:
    score = 20
    if phone:
        score += 25
    if email:
        score += 25
    if website:
        score += 15
    if address:
        score += 10
    return max(0, min(100, score))


def _decimal_to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _history_to_payload(history: UserLeadHistory) -> dict:
    lead = history.lead
    company_name = lead.company_name

    return {
        "id": str(history.id),
        "_id": str(history.id),
        "lead_id": str(lead.id),
        "user_id": str(history.user_id),
        "status": history.status.value,
        "_status": history.status.value,
        "score": history.score,
        "chance_fechamento": float(history.chance_fechamento or 0),
        "ticket_estimado": _decimal_to_float(history.ticket_estimado),
        "ultimo_contato": history.ultimo_contato.isoformat() if history.ultimo_contato else None,
        "proximo_follow_up": history.proximo_follow_up.isoformat() if history.proximo_follow_up else None,
        "observacoes": history.observacoes,
        "created_at": history.created_at.isoformat() if history.created_at else None,
        "updated_at": history.updated_at.isoformat() if history.updated_at else None,
        "_created": history.created_at.isoformat() if history.created_at else None,
        "_updated": history.updated_at.isoformat() if history.updated_at else None,
        # canonical
        "company_name": company_name,
        "phone": lead.phone,
        "email": lead.email,
        "address": lead.address,
        "website": lead.website,
        "rating": lead.rating,
        "city": lead.city,
        "country": lead.country,
        "niche": lead.niche,
        "source": lead.source,
        # backward compatible aliases for current UI
        "empresa": company_name,
        "telefone": lead.phone,
        "site": lead.website,
        "cidade": lead.city,
        "pais": lead.country,
        "nicho": lead.niche,
        "origem": lead.source,
        "extra_data": history.lead_data or lead.raw_data or {},
    }


def _apply_filters(query, *, status_filter: str | None, cidade: str | None, pais: str | None, nicho: str | None, search: str | None):
    parsed_status = _lead_status(status_filter)
    if parsed_status:
        query = query.filter(UserLeadHistory.status == parsed_status)

    if cidade:
        query = query.filter(Lead.city.ilike(f"%{cidade.strip()}%"))
    if pais:
        query = query.filter(Lead.country.ilike(f"%{pais.strip()}%"))
    if nicho:
        query = query.filter(Lead.niche.ilike(f"%{nicho.strip()}%"))

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Lead.company_name.ilike(term),
                Lead.phone.ilike(term),
                Lead.email.ilike(term),
                Lead.website.ilike(term),
                Lead.address.ilike(term),
                Lead.city.ilike(term),
                Lead.country.ilike(term),
            )
        )

    return query


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

    query = db.query(UserLeadHistory).join(Lead, UserLeadHistory.lead_id == Lead.id).filter(UserLeadHistory.user_id == user.id)
    query = _apply_filters(query, status_filter=status_filter, cidade=cidade, pais=pais, nicho=nicho, search=search)

    total = query.count()

    sort_map = {
        "created_at": UserLeadHistory.created_at,
        "updated_at": UserLeadHistory.updated_at,
        "empresa": Lead.company_name,
        "company_name": Lead.company_name,
        "cidade": Lead.city,
        "city": Lead.city,
        "pais": Lead.country,
        "country": Lead.country,
        "status": UserLeadHistory.status,
        "score": UserLeadHistory.score,
        "ticket_estimado": UserLeadHistory.ticket_estimado,
        "chance_fechamento": UserLeadHistory.chance_fechamento,
    }
    sort_column = sort_map.get(sort_by, UserLeadHistory.created_at)
    order_by = sort_column.asc() if sort_dir.lower() == "asc" else desc(sort_column)

    rows = query.order_by(order_by).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    stats_rows = (
        db.query(UserLeadHistory.status, func.count(UserLeadHistory.id))
        .filter(UserLeadHistory.user_id == user.id)
        .group_by(UserLeadHistory.status)
        .all()
    )
    stats = {row[0].value: row[1] for row in stats_rows}
    stats["total"] = sum(stats.values())

    countries = [
        value
        for (value,) in (
            db.query(Lead.country)
            .join(UserLeadHistory, UserLeadHistory.lead_id == Lead.id)
            .filter(and_(UserLeadHistory.user_id == user.id, Lead.country.isnot(None), Lead.country != ""))
            .distinct()
            .order_by(Lead.country.asc())
            .all()
        )
    ]

    return {
        "leads": [_history_to_payload(item) for item in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "stats": stats,
        "countries": countries,
    }


def get_lead(db: Session, user: User, lead_id: str) -> UserLeadHistory:
    parsed_id = _parse_id(lead_id)
    row = (
        db.query(UserLeadHistory)
        .join(Lead, UserLeadHistory.lead_id == Lead.id)
        .filter(UserLeadHistory.id == parsed_id, UserLeadHistory.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return row


def serialize_lead(history: UserLeadHistory) -> dict:
    return _history_to_payload(history)


def update_lead(db: Session, user: User, lead_id: str, payload: dict) -> dict:
    row = get_lead(db, user, lead_id)

    if payload.get("status"):
        row.status = LeadStatus(payload["status"])
    if payload.get("ticket_estimado") is not None:
        row.ticket_estimado = payload["ticket_estimado"]
    if payload.get("chance_fechamento") is not None:
        row.chance_fechamento = payload["chance_fechamento"]
    if payload.get("proximo_follow_up") is not None:
        row.proximo_follow_up = payload["proximo_follow_up"]
    if payload.get("ultimo_contato") is not None:
        row.ultimo_contato = payload["ultimo_contato"]
    if payload.get("observacoes") is not None:
        row.observacoes = payload["observacoes"]
    if payload.get("score") is not None:
        row.score = payload["score"]

    row.updated_at = _now_utc()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _history_to_payload(row)


def delete_lead(db: Session, user: User, lead_id: str) -> None:
    row = get_lead(db, user, lead_id)
    db.delete(row)
    db.commit()


def bulk_update_status(db: Session, user: User, lead_ids: list[str], status: str) -> int:
    if not lead_ids:
        return 0
    parsed_ids = [_parse_id(item) for item in lead_ids]
    updated = (
        db.query(UserLeadHistory)
        .filter(UserLeadHistory.user_id == user.id, UserLeadHistory.id.in_(parsed_ids))
        .update({UserLeadHistory.status: LeadStatus(status), UserLeadHistory.updated_at: _now_utc()}, synchronize_session=False)
    )
    db.commit()
    return int(updated)


def _coerce_raw_lead(raw: dict) -> dict | None:
    company_name = str(raw.get("company_name") or raw.get("empresa") or raw.get("nome_empresa") or "").strip()
    if not company_name:
        return None

    city = str(raw.get("city") or raw.get("cidade") or "").strip() or None
    phone = str(raw.get("phone") or raw.get("telefone") or "").strip() or None

    return {
        "company_name": company_name,
        "phone": phone,
        "email": str(raw.get("email") or "").strip().lower() or None,
        "address": str(raw.get("address") or raw.get("endereco") or "").strip() or None,
        "website": str(raw.get("website") or raw.get("site") or "").strip() or None,
        "rating": raw.get("rating"),
        "city": city,
        "country": str(raw.get("country") or raw.get("pais") or "Brasil").strip() or "Brasil",
        "niche": str(raw.get("niche") or raw.get("nicho") or "").strip() or None,
        "source": str(raw.get("source") or raw.get("origem") or "ai_scraper").strip() or "ai_scraper",
        "raw": raw,
    }


def upsert_leads(db: Session, user: User, leads_payload: list[dict]) -> dict:
    if not leads_payload:
        return {"inserted": 0, "duplicates": 0, "total_received": 0}

    prepared: list[dict] = []
    hashes: list[str] = []

    for raw in leads_payload:
        item = _coerce_raw_lead(raw)
        if not item:
            continue
        lead_hash = _lead_hash(item["company_name"], item.get("city"), item.get("phone"))
        item["lead_hash"] = lead_hash
        prepared.append(item)
        hashes.append(lead_hash)

    if not prepared:
        return {"inserted": 0, "duplicates": 0, "total_received": len(leads_payload)}

    existing_user_hashes = {
        value
        for (value,) in (
            db.query(UserLeadHistory.lead_hash)
            .filter(UserLeadHistory.user_id == user.id, UserLeadHistory.lead_hash.in_(hashes))
            .all()
        )
    }

    existing_global = {
        row.lead_hash: row
        for row in db.query(Lead).filter(Lead.lead_hash.in_(hashes)).all()
    }

    inserted = 0
    duplicates = 0

    for item in prepared:
        lead_hash = item["lead_hash"]

        if lead_hash in existing_user_hashes:
            duplicates += 1
            continue

        lead = existing_global.get(lead_hash)
        if not lead:
            lead = Lead(
                lead_hash=lead_hash,
                company_name=item["company_name"],
                phone=item["phone"],
                email=item["email"],
                address=item["address"],
                website=item["website"],
                rating=float(item["rating"]) if item.get("rating") not in (None, "") else None,
                city=item["city"],
                country=item["country"],
                niche=item["niche"],
                source=item["source"],
                raw_data=item["raw"],
            )
            db.add(lead)
            db.flush()
            existing_global[lead_hash] = lead

        score = _compute_score(item["phone"], item["email"], item["website"], item["address"])
        chance = round(max(8.0, min(92.0, score * 0.78)), 1)
        ticket = round(1200 + (score * 35), 2)

        history = UserLeadHistory(
            user_id=user.id,
            lead_id=lead.id,
            lead_hash=lead_hash,
            status=LeadStatus.novos,
            score=score,
            chance_fechamento=chance,
            ticket_estimado=ticket,
            observacoes=None,
            lead_data=item["raw"],
        )
        db.add(history)
        existing_user_hashes.add(lead_hash)
        inserted += 1

    db.commit()

    return {
        "inserted": inserted,
        "duplicates": duplicates,
        "total_received": len(leads_payload),
    }


def export_csv_content(db: Session, user: User) -> str:
    rows = (
        db.query(UserLeadHistory)
        .join(Lead, UserLeadHistory.lead_id == Lead.id)
        .filter(UserLeadHistory.user_id == user.id)
        .order_by(UserLeadHistory.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "lead_id",
            "company_name",
            "phone",
            "email",
            "website",
            "address",
            "city",
            "country",
            "niche",
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

    for row in rows:
        lead = row.lead
        writer.writerow(
            [
                str(row.id),
                str(lead.id),
                lead.company_name,
                lead.phone or "",
                lead.email or "",
                lead.website or "",
                lead.address or "",
                lead.city or "",
                lead.country or "",
                lead.niche or "",
                row.status.value,
                row.score,
                _decimal_to_float(row.ticket_estimado),
                float(row.chance_fechamento or 0),
                row.ultimo_contato.isoformat() if row.ultimo_contato else "",
                row.proximo_follow_up.isoformat() if row.proximo_follow_up else "",
                row.observacoes or "",
                row.created_at.isoformat() if row.created_at else "",
            ]
        )

    return output.getvalue()
