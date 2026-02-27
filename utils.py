import asyncio
import json
import os
import random
import time
from typing import Iterable

import pandas as pd


# Colunas exigidas no CSV final
COLUMNS = [
    "pais",
    "nicho",
    "nome_empresa",
    "cidade",
    "endereco",
    "telefone",
    "email",
    "instagram",
    "site",
    "linkedin",
    "fonte_link",
    "observacoes",
]


def _get_delay_range(min_s: float | None, max_s: float | None) -> tuple[float, float]:
    if min_s is None:
        min_s = float(os.getenv("DELAY_MIN", "1.8"))
    if max_s is None:
        max_s = float(os.getenv("DELAY_MAX", "6"))
    return min_s, max_s


async def random_delay(min_s: float | None = None, max_s: float | None = None) -> None:
    """Delay aleatorio para reduzir padroes de scraping."""
    min_s, max_s = _get_delay_range(min_s, max_s)
    await asyncio.sleep(random.uniform(min_s, max_s))


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(value, max_value))


def add_observacao(lead: dict, obs: str) -> None:
    """Garante observacoes unicas em formato CSV."""
    observacoes = lead.get("observacoes", "")
    obs_set = {o.strip() for o in observacoes.split(",") if o.strip()}
    obs_set.add(obs)
    lead["observacoes"] = ",".join(sorted(obs_set))


class CircuitBreaker:
    """Circuit breaker simples para evitar loops de erro continuos."""

    def __init__(self, fail_threshold: int = 5, cooloff_s: int = 60) -> None:
        self.fail_threshold = fail_threshold
        self.cooloff_s = cooloff_s
        self.fail_count = 0
        self.open_until = 0.0

    def allow(self) -> bool:
        if self.open_until == 0:
            return True
        return time.time() >= self.open_until

    def record_success(self) -> None:
        self.fail_count = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self.open_until = time.time() + self.cooloff_s


def normalize_leads(leads: Iterable[dict]) -> list[dict]:
    """Normaliza campos ausentes para garantir o schema."""
    normalized: list[dict] = []
    for lead in leads:
        item = {key: lead.get(key, "") or "" for key in COLUMNS}
        # Preserva campos extras em JSON
        for k, v in lead.items():
            if k not in item:
                item[k] = v
        normalized.append(item)
    return normalized


def dedupe_leads_local(leads: Iterable[dict]) -> list[dict]:
    """Remove duplicatas localmente por nome+site+telefone."""
    seen = set()
    unique: list[dict] = []

    for lead in leads:
        key = (
            (lead.get("nome_empresa") or "").lower(),
            (lead.get("site") or "").lower(),
            (lead.get("telefone") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(lead)

    return unique


def save_csv(leads: list[dict], path: str) -> None:
    """Salva CSV com encoding compativel com Excel."""
    if not leads:
        df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(leads)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS]
    df.to_csv(path, index=False, encoding="utf-8-sig")


def save_json(leads: list[dict], path: str) -> None:
    """Salva JSON completo com dados brutos."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)


async def retry_async(
    action,
    retries: int = 3,
    min_s: float = 1.8,
    max_s: float = 6,
    breaker: CircuitBreaker | None = None,
) -> object:
    """Retry simples com backoff exponencial (async) e circuit breaker."""
    last_error = None
    for attempt in range(retries):
        if breaker and not breaker.allow():
            raise RuntimeError("Circuit breaker aberto")
        try:
            result = await action()
            if breaker:
                breaker.record_success()
            return result
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if breaker:
                breaker.record_failure()
            await random_delay(min_s=min_s * (1.5 ** attempt), max_s=max_s * (1.5 ** attempt))
    if last_error:
        raise last_error
    return None


def build_output_stats(leads: list[dict]) -> dict:
    """Resumo estatistico final para o usuario."""
    total = max(1, len(leads))
    with_email = sum(1 for l in leads if l.get("email"))
    with_ig = sum(1 for l in leads if l.get("instagram"))
    with_wa = sum(1 for l in leads if "tem_wa" in (l.get("observacoes") or ""))
    procura = sum(1 for l in leads if "procura-servico" in (l.get("observacoes") or ""))

    def pct(value: int) -> str:
        return f"{(value / total) * 100:.1f}%"

    return {
        "Total de leads": len(leads),
        "Com email": f"{with_email} ({pct(with_email)})",
        "Com Instagram": f"{with_ig} ({pct(with_ig)})",
        "Com WhatsApp": f"{with_wa} ({pct(with_wa)})",
        "Procura-servico": f"{procura} ({pct(procura)})",
    }


def export_to_gsheets(
    leads: list[dict],
    sheet_id: str | None,
    credentials_path: str | None,
    worksheet_name: str,
    columns: list[str],
) -> None:
    """Export opcional para Google Sheets usando gspread."""
    if not sheet_id or not credentials_path:
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception:
        return

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(creds)

    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except Exception:
        ws = sh.add_worksheet(title=worksheet_name, rows="1000", cols=str(len(columns)))

    rows = [columns]
    for lead in leads:
        rows.append([lead.get(col, "") for col in columns])

    ws.clear()
    ws.update(rows)
