import json
from datetime import datetime

from sqlalchemy import text
from server.services.db import get_conn

VALID_SORT = {
    "id": "id",
    "status": "COALESCE(status, 'novo')",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "nome_empresa": "LOWER(COALESCE(json_extract(data_json, '$.nome_empresa'), ''))",
    "cidade": "LOWER(COALESCE(json_extract(data_json, '$.cidade'), ''))",
    "pais": "LOWER(COALESCE(json_extract(data_json, '$.pais'), ''))",
}
VALID_STATUSES = {"novo", "contatado", "fechado", "ignorado"}
COUNTRY_ALIASES = {
    "Brasil": ["Brasil", "Brazil"],
    "Portugal": ["Portugal"],
    "Estados Unidos": ["Estados Unidos", "EUA", "USA", "United States", "United States of America"],
    "Canadá": ["Canadá", "Canada"],
    "Austrália": ["Austrália", "Australia"],
}
DEFAULT_COUNTRIES = list(COUNTRY_ALIASES.keys())
COUNTRY_LOOKUP = {
    alias.lower(): canonical
    for canonical, aliases in COUNTRY_ALIASES.items()
    for alias in [canonical, *aliases]
}


def _parse_lead(row) -> dict:
    try:
        data = json.loads(row["data_json"])
    except Exception:
        data = {}
    data["_id"] = row["id"]
    data["_status"] = row["status"] or "novo"
    data["_created"] = row["created_at"] or ""
    data["_updated"] = row["updated_at"] or ""
    return data


def _canonical_country(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    return COUNTRY_LOOKUP.get(raw.lower(), raw)


def _country_variants(value: str) -> list[str]:
    canonical = _canonical_country(value)
    return COUNTRY_ALIASES.get(canonical, [canonical])


def get_leads(
    status: str | None = None,
    pais: str | None = None,
    cidade: str | None = None,
    search: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "id",
    sort_dir: str = "desc",
) -> dict:
    if sort_by not in VALID_SORT:
        sort_by = "id"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    page = max(1, page)
    per_page = max(1, min(per_page, 200))

    with get_conn(row_factory=True) as conn:

        where = ["1=1"]
        params_dict: dict = {}

        if status and status != "todos":
            where.append("COALESCE(status,'novo') = :status")
            params_dict["status"] = status

        if pais and pais != "todos":
            variants = [item.lower() for item in _country_variants(pais)]
            placeholders = ",".join(f":country_{i}" for i in range(len(variants)))
            where.append(
                f"LOWER(COALESCE(json_extract(data_json, '$.pais'), '')) IN ({placeholders})"
            )
            for i, v in enumerate(variants):
                params_dict[f"country_{i}"] = v

        if cidade:
            where.append("LOWER(COALESCE(json_extract(data_json, '$.cidade'), '')) LIKE :cidade")
            params_dict["cidade"] = f"%{cidade.lower()}%"

        if search:
            term = f"%{search.lower()}%"
            where.append(
                "("
                "LOWER(COALESCE(json_extract(data_json, '$.nome_empresa'), '')) LIKE :term OR "
                "LOWER(COALESCE(json_extract(data_json, '$.telefone'), '')) LIKE :term OR "
                "LOWER(COALESCE(json_extract(data_json, '$.email'), '')) LIKE :term OR "
                "LOWER(COALESCE(json_extract(data_json, '$.cidade'), '')) LIKE :term OR "
                "LOWER(COALESCE(json_extract(data_json, '$.site'), '')) LIKE :term"
                ")"
            )
            params_dict["term"] = term

        if created_from:
            where.append("substr(COALESCE(created_at, ''), 1, 10) >= :created_from")
            params_dict["created_from"] = created_from[:10]

        if created_to:
            where.append("substr(COALESCE(created_at, ''), 1, 10) <= :created_to")
            params_dict["created_to"] = created_to[:10]

        where_sql = " AND ".join(where)
        sort_sql = VALID_SORT.get(sort_by, VALID_SORT["id"])

        row = conn.execute(
            text(f"SELECT COUNT(*) FROM leads WHERE {where_sql}"), params_dict
        ).fetchone()
        total = row[0] if row else 0

        offset = (page - 1) * per_page
        params_dict["per_page"] = per_page
        params_dict["offset"] = offset
        
        rows = conn.execute(
            text(
                f"SELECT id, COALESCE(status,'novo') as status, created_at, updated_at, data_json "
                f"FROM leads WHERE {where_sql} ORDER BY {sort_sql} {sort_dir} "
                f"LIMIT :per_page OFFSET :offset"
            ),
            params_dict,
        ).fetchall()

    pages = max(1, (total + per_page - 1) // per_page)

    return {
        "leads": [_parse_lead(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_stats() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            text("SELECT COALESCE(status,'novo') as s, COUNT(*) FROM leads GROUP BY s")
        ).fetchall()
    stats = {r[0]: r[1] for r in rows}
    stats["total"] = sum(stats.values())
    return stats


def get_countries() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT TRIM(COALESCE(json_extract(data_json, '$.pais'), '')) as pais FROM leads")
        ).fetchall()
    countries = {_canonical_country(row[0]) for row in rows if row and row[0]}
    countries.update(DEFAULT_COUNTRIES)
    ordered = [name for name in DEFAULT_COUNTRIES if name in countries]
    tail = sorted(name for name in countries if name not in DEFAULT_COUNTRIES)
    return ordered + tail


def mark_leads(ids: list[int], status: str) -> int:
    if not ids or status not in VALID_STATUSES:
        return 0
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    
    placeholders = ",".join(f":id_{i}" for i in range(len(ids)))
    params_dict: dict[str, str | int] = {f"id_{i}": val for i, val in enumerate(ids)}
    params_dict["status"] = status
    params_dict["updated_at"] = now
    
    with get_conn() as conn:
        cur = conn.execute(
            text(f"UPDATE leads SET status = :status, updated_at = :updated_at WHERE id IN ({placeholders})"),
            params_dict,
        )
        conn.commit()
    return getattr(cur, "rowcount", 0)


def delete_leads(ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join(f":id_{i}" for i in range(len(ids)))
    params_dict: dict[str, str | int] = {f"id_{i}": val for i, val in enumerate(ids)}
    with get_conn() as conn:
        cur = conn.execute(text(f"DELETE FROM leads WHERE id IN ({placeholders})"), params_dict)
        conn.commit()
    return getattr(cur, "rowcount", 0)


def delete_by_status(status: str) -> int:
    if status not in VALID_STATUSES:
        return 0

    with get_conn() as conn:
        cur = conn.execute(
            text("DELETE FROM leads WHERE COALESCE(status,'novo') = :status"), {"status": status}
        )
        conn.commit()
    return getattr(cur, "rowcount", 0)


def get_lead_detail(lead_id: int) -> dict | None:
    with get_conn(row_factory=True) as conn:
        row = conn.execute(
            text(
                "SELECT id, COALESCE(status,'novo') as status, created_at, updated_at, data_json "
                "FROM leads WHERE id = :lead_id"
            ),
            {"lead_id": lead_id},
        ).fetchone()
    if not row:
        return None
    return _parse_lead(row)
