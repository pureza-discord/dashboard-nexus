from collections import defaultdict
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.db.models import Lead, LeadStatus, User


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def get_overview(db: Session, user: User) -> dict:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    leads = db.query(Lead).filter(Lead.user_id == user.id).all()

    total = len(leads)
    pipeline_counts = defaultdict(int)
    potential_revenue = 0.0
    expected_revenue = 0.0
    leads_this_month = 0

    by_niche: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "closed": 0})
    by_city: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "closed": 0})
    revenue_by_month: dict[str, float] = defaultdict(float)

    for lead in leads:
        stage = lead.status.value
        pipeline_counts[stage] += 1

        ticket = _safe_float(lead.ticket_estimado)
        chance = _safe_float(lead.chance_fechamento)

        if lead.status != LeadStatus.perdidos:
            potential_revenue += ticket
        expected_revenue += ticket * (chance / 100.0)

        if lead.created_at and lead.created_at >= month_start:
            leads_this_month += 1

        niche_key = (lead.nicho or "Sem nicho").strip() or "Sem nicho"
        city_key = (lead.cidade or "Sem cidade").strip() or "Sem cidade"

        by_niche[niche_key]["total"] += 1
        by_city[city_key]["total"] += 1

        if lead.status == LeadStatus.fechados:
            by_niche[niche_key]["closed"] += 1
            by_city[city_key]["closed"] += 1
            month_label = lead.updated_at.strftime("%Y-%m") if lead.updated_at else now.strftime("%Y-%m")
            revenue_by_month[month_label] += ticket

    closed = pipeline_counts[LeadStatus.fechados.value]
    conversion_rate = (closed / max(total, 1)) * 100.0

    pipeline = [
        {"stage": LeadStatus.novos.value, "label": "Novos", "count": pipeline_counts[LeadStatus.novos.value]},
        {
            "stage": LeadStatus.contatados.value,
            "label": "Contatados",
            "count": pipeline_counts[LeadStatus.contatados.value],
        },
        {
            "stage": LeadStatus.proposta.value,
            "label": "Proposta",
            "count": pipeline_counts[LeadStatus.proposta.value],
        },
        {
            "stage": LeadStatus.fechados.value,
            "label": "Fechados",
            "count": pipeline_counts[LeadStatus.fechados.value],
        },
        {
            "stage": LeadStatus.perdidos.value,
            "label": "Perdidos",
            "count": pipeline_counts[LeadStatus.perdidos.value],
        },
    ]

    conversion_by_niche = [
        {
            "nicho": niche,
            "total": values["total"],
            "closed": values["closed"],
            "conversion_rate": round((values["closed"] / max(values["total"], 1)) * 100.0, 2),
        }
        for niche, values in sorted(by_niche.items(), key=lambda item: item[1]["total"], reverse=True)
    ]

    conversion_by_city = [
        {
            "cidade": city,
            "total": values["total"],
            "closed": values["closed"],
            "conversion_rate": round((values["closed"] / max(values["total"], 1)) * 100.0, 2),
        }
        for city, values in sorted(by_city.items(), key=lambda item: item[1]["total"], reverse=True)
    ]

    revenue_series = [
        {"month": month, "revenue": round(value, 2)}
        for month, value in sorted(revenue_by_month.items(), key=lambda item: item[0])
    ]

    # Snapshot for last 6 months even when there is no closed deal.
    month_cursor = month_start
    last_six = []
    for _ in range(6):
        label = month_cursor.strftime("%Y-%m")
        last_six.append({"month": label, "revenue": round(revenue_by_month.get(label, 0.0), 2)})
        if month_cursor.month == 1:
            month_cursor = month_cursor.replace(year=month_cursor.year - 1, month=12)
        else:
            month_cursor = month_cursor.replace(month=month_cursor.month - 1)

    return {
        "leads_this_month": leads_this_month,
        "total_leads": total,
        "potential_revenue": round(potential_revenue, 2),
        "expected_revenue": round(expected_revenue, 2),
        "conversion_rate": round(conversion_rate, 2),
        "pipeline": pipeline,
        "conversion_by_niche": conversion_by_niche,
        "conversion_by_city": conversion_by_city,
        "revenue_by_month": revenue_series or list(reversed(last_six)),
    }


def quick_metrics(db: Session, user: User) -> dict:
    closed_count = (
        db.query(func.count(Lead.id))
        .filter(Lead.user_id == user.id, Lead.status == LeadStatus.fechados)
        .scalar()
        or 0
    )
    total_count = db.query(func.count(Lead.id)).filter(Lead.user_id == user.id).scalar() or 0

    return {
        "total": int(total_count),
        "closed": int(closed_count),
        "conversion_rate": round((closed_count / max(total_count, 1)) * 100, 2),
    }

