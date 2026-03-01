import json
from collections import defaultdict
from datetime import datetime, timedelta

from server.config import AVERAGE_DEAL_VALUE
from server.services.db import get_conn


def get_analytics() -> dict:
    with get_conn(row_factory=True) as conn:
        rows = conn.execute(
            "SELECT id, COALESCE(status,'novo') as status, created_at, data_json FROM leads"
        ).fetchall()

    status_counts: dict[str, int] = defaultdict(int)
    country_counts: dict[str, int] = defaultdict(int)
    daily_counts: dict[str, int] = defaultdict(int)

    for r in rows:
        status_counts[r["status"]] += 1

        try:
            d = json.loads(r["data_json"])
            pais = d.get("pais", "Desconhecido")
            country_counts[pais] += 1
        except Exception:
            pass

        created = r["created_at"] or ""
        if created:
            day = created[:10]
            daily_counts[day] += 1

    total = sum(status_counts.values())
    fechados = status_counts.get("fechado", 0)
    contatados = status_counts.get("contatado", 0)
    novos = status_counts.get("novo", 0)
    ignorados = status_counts.get("ignorado", 0)

    conversion_rate = (fechados / max(total, 1)) * 100
    contact_rate = (contatados / max(total, 1)) * 100
    estimated_revenue = fechados * AVERAGE_DEAL_VALUE

    today = datetime.utcnow().date()
    last_30 = []
    for i in range(29, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        last_30.append({"date": day, "count": daily_counts.get(day, 0)})

    funnel = [
        {"stage": "Novos", "count": novos, "color": "#10b981"},
        {"stage": "Contatados", "count": contatados, "color": "#f59e0b"},
        {"stage": "Fechados", "count": fechados, "color": "#3b82f6"},
        {"stage": "Ignorados", "count": ignorados, "color": "#71717a"},
    ]

    by_country = [
        {"country": k, "count": v}
        for k, v in sorted(country_counts.items(), key=lambda x: -x[1])
    ]

    return {
        "total": total,
        "novo": novos,
        "contatado": contatados,
        "fechado": fechados,
        "ignorado": ignorados,
        "conversion_rate": round(conversion_rate, 1),
        "contact_rate": round(contact_rate, 1),
        "estimated_revenue": estimated_revenue,
        "average_deal_value": AVERAGE_DEAL_VALUE,
        "leads_per_day": last_30,
        "funnel": funnel,
        "by_country": by_country,
    }
