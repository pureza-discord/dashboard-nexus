import hashlib
import json
import sqlite3
from datetime import datetime


class Database:
    """SQLite com deduplicação, histórico e tracking de status."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_hash TEXT UNIQUE,
                    created_at TEXT,
                    data_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_hash ON leads(lead_hash)")

            # Migração: adiciona colunas novas se não existem
            cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
            if "status" not in cols:
                conn.execute("ALTER TABLE leads ADD COLUMN status TEXT DEFAULT 'novo'")
            if "updated_at" not in cols:
                conn.execute("ALTER TABLE leads ADD COLUMN updated_at TEXT")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
            conn.commit()

    def _hash_lead(self, lead: dict) -> str:
        base = "|".join(
            [
                (lead.get("nome_empresa") or "").lower(),
                (lead.get("site") or "").lower(),
                (lead.get("telefone") or "").lower(),
                (lead.get("cidade") or "").lower(),
            ]
        )
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Inserção / Filtragem
    # ------------------------------------------------------------------

    def filter_new_leads(self, leads: list[dict]) -> list[dict]:
        if not leads:
            return []
        hashes = [self._hash_lead(l) for l in leads]
        with sqlite3.connect(self.path) as conn:
            ph = ",".join("?" for _ in hashes)
            existing = {
                row[0]
                for row in conn.execute(
                    f"SELECT lead_hash FROM leads WHERE lead_hash IN ({ph})", hashes
                ).fetchall()
            }
        return [lead for lead, h in zip(leads, hashes) if h not in existing]

    def upsert_leads(self, leads: list[dict]) -> None:
        if not leads:
            return
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with sqlite3.connect(self.path) as conn:
            for lead in leads:
                h = self._hash_lead(lead)
                data = json.dumps(lead, ensure_ascii=False)
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO leads (lead_hash, status, created_at, updated_at, data_json) "
                        "VALUES (?, 'novo', ?, ?, ?)",
                        (h, now, now, data),
                    )
                except sqlite3.Error:
                    continue
            conn.commit()

    # ------------------------------------------------------------------
    # Status management
    # ------------------------------------------------------------------

    def mark(self, lead_id: int, status: str) -> bool:
        """Marca um lead como 'contatado', 'fechado', 'ignorado', etc."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, lead_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def mark_by_name(self, nome: str, status: str) -> int:
        """Marca leads que contenham o nome (busca parcial)."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                "UPDATE leads SET status = ?, updated_at = ? "
                "WHERE LOWER(data_json) LIKE ?",
                (status, now, f"%{nome.lower()}%"),
            )
            conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def get_leads(self, status: str | None = None) -> list[dict]:
        """Retorna leads. Se status=None retorna todos."""
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT id, status, created_at, data_json FROM leads WHERE status = ? ORDER BY id",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, status, created_at, data_json FROM leads ORDER BY id"
                ).fetchall()

        result = []
        for row in rows:
            try:
                lead = json.loads(row["data_json"])
            except (json.JSONDecodeError, TypeError):
                lead = {}
            lead["_id"] = row["id"]
            lead["_status"] = row["status"] or "novo"
            lead["_created_at"] = row["created_at"]
            result.append(lead)
        return result

    def count_by_status(self) -> dict[str, int]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT COALESCE(status, 'novo') as s, COUNT(*) FROM leads GROUP BY s"
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    def purge(self, status: str) -> int:
        """Remove leads com determinado status."""
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("DELETE FROM leads WHERE status = ?", (status,))
            conn.commit()
            return cur.rowcount
