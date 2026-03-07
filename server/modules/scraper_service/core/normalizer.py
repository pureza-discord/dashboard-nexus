"""Normalize scraped lead data into a consistent schema."""

import hashlib
import re
from urllib.parse import urlparse


LEAD_FIELDS = [
    "empresa", "telefone", "email", "site", "cidade", "estado",
    "pais", "nicho", "origem", "observacoes",
]


def _extract_domain(site: str) -> str:
    """Extract clean domain from a URL for fingerprinting."""
    if not site:
        return ""
    try:
        parsed = urlparse(site if "://" in site else f"https://{site}")
        domain = (parsed.netloc or parsed.path).lower().strip()
        # Remove www. prefix
        domain = re.sub(r"^www\.", "", domain)
        # Remove port
        domain = domain.split(":")[0]
        return domain
    except Exception:
        return ""


def normalize_lead(raw: dict, *, nicho: str, pais: str, cidade: str | None, source: str) -> dict:
    """Normalize a raw scraped lead into the standard schema."""
    return {
        "empresa": (raw.get("nome_empresa") or raw.get("empresa") or "").strip() or "Unknown",
        "telefone": (raw.get("telefone") or "").strip() or None,
        "email": (raw.get("email") or "").strip() or None,
        "site": (raw.get("site") or "").strip() or None,
        "cidade": (raw.get("cidade") or cidade or "").strip() or None,
        "estado": (raw.get("estado") or "").strip() or None,
        "pais": (raw.get("pais") or pais).strip(),
        "nicho": (raw.get("nicho") or nicho).strip(),
        "origem": source,
        "observacoes": (raw.get("observacoes") or "").strip(),
    }


def normalize_leads(raws: list[dict], *, nicho: str, pais: str, cidade: str | None, source: str) -> list[dict]:
    """Normalize a batch of raw leads."""
    return [normalize_lead(r, nicho=nicho, pais=pais, cidade=cidade, source=source) for r in raws]


def dedup_fingerprint(lead: dict) -> str:
    """Generate a dedup fingerprint from name + phone + domain.

    Uses multiple signals for stronger deduplication:
    - Company name (normalized)
    - Phone number (digits only)
    - Domain from website URL
    """
    nome = (lead.get("empresa") or lead.get("nome_empresa") or "").strip().lower()
    telefone = re.sub(r"[^\d]", "", lead.get("telefone") or "")
    domain = _extract_domain(lead.get("site") or "")
    base = f"{nome}|{telefone}|{domain}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def deduplicate(leads: list[dict]) -> list[dict]:
    """Remove duplicates by name + phone + domain fingerprint."""
    seen: set[str] = set()
    unique: list[dict] = []
    for lead in leads:
        fp = dedup_fingerprint(lead)
        if fp in seen:
            continue
        seen.add(fp)
        unique.append(lead)
    return unique

