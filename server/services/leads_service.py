import json
import sqlite3
from datetime import datetime

from server.config import DB_PATH

VALID_SORT = {"id", "status", "created_at", "updated_at"}
VALID_STATUSES = {"novo", "contatado", "fechado", "ignorado"}


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


def get_leads(
    status: str | None = None,
    pais: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "id",
    sort_dir: str = "desc",
) -> dict:
    if sort_by not in VALID_SORT:
        sort_by = "id"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        where = ["1=1"]
        params: list = []

        if status and status != "todos":
            where.append("COALESCE(status,'novo') = ?")
            params.append(status)

        if pais and pais != "todos":
            where.append("LOWER(data_json) LIKE ?")
            params.append(f'%"pais": "{pais}"%')

        if search:
            where.append("LOWER(data_json) LIKE ?")
            params.append(f"%{search.lower()}%")

        where_sql = " AND ".join(where)

        total = conn.execute(
            f"SELECT COUNT(*) FROM leads WHERE {where_sql}", params
        ).fetchone()[0]

        offset = (max(1, page) - 1) * per_page
        rows = conn.execute(
            f"SELECT id, COALESCE(status,'novo') as status, created_at, updated_at, data_json "
            f"FROM leads WHERE {where_sql} ORDER BY {sort_by} {sort_dir} "
            f"LIMIT ? OFFSET ?",
            params + [per_page, offset],
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
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT COALESCE(status,'novo') as s, COUNT(*) FROM leads GROUP BY s"
        ).fetchall()
    stats = {r[0]: r[1] for r in rows}
    stats["total"] = sum(stats.values())
    return stats


def get_countries() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT data_json FROM leads").fetchall()
    countries: set[str] = set()
    for r in rows:
        try:
            d = json.loads(r[0])
            p = d.get("pais", "")
            if p:
                countries.add(p)
        except Exception:
            pass
    return sorted(countries)


def mark_leads(ids: list[int], status: str) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with sqlite3.connect(DB_PATH) as conn:
        count = 0
        for lid in ids:
            cur = conn.execute(
                "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, lid),
            )
            count += cur.rowcount
        conn.commit()
    return count


def delete_leads(ids: list[int]) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        count = 0
        for lid in ids:
            cur = conn.execute("DELETE FROM leads WHERE id = ?", (lid,))
            count += cur.rowcount
        conn.commit()
    return count


def delete_by_status(status: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM leads WHERE COALESCE(status,'novo') = ?", (status,)
        )
        conn.commit()
    return cur.rowcount


def get_lead_detail(lead_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, COALESCE(status,'novo') as status, created_at, updated_at, data_json "
            "FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
    if not row:
        return None
    return _parse_lead(row)
