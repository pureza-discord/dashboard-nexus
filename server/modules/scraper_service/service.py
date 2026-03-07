from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Callable

import httpx
from outscraper import ApiClient as OutscraperClient

from server.core.settings import get_settings

settings = get_settings()
logger = logging.getLogger("scraper_service")

ProgressCallback = Callable[[int, str], None]


@dataclass(slots=True)
class ScrapeRequest:
    nicho: str
    cidade: str | None
    pais: str
    quantidade: int
    aleatorio: bool = False


def _coerce_quantity(quantity: int | str | None) -> int:
    try:
        value = int(quantity or 5)
    except Exception:
        value = 5
    return max(1, min(value, 100))


def _lead_hash(company_name: str, city: str | None, phone: str | None) -> str:
    base = f"{(company_name or '').strip().lower()}|{(city or '').strip().lower()}|{(phone or '').strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _normalize_lead(raw: dict, *, niche: str, country: str, fallback_city: str | None, source: str) -> dict | None:
    company_name = (
        raw.get("company_name")
        or raw.get("name")
        or raw.get("title")
        or raw.get("business_name")
        or ""
    )
    company_name = str(company_name).strip()
    if not company_name:
        return None

    phone = raw.get("phone") or raw.get("phone_number") or raw.get("primary_phone")

    email = (
        raw.get("email")
        or raw.get("emails")
        or raw.get("emails_1")
        or raw.get("business_email")
    )
    if isinstance(email, list):
        email = email[0] if email else None

    website = raw.get("website") or raw.get("site") or raw.get("domain") or raw.get("link")
    address = raw.get("address") or raw.get("full_address") or raw.get("street")
    rating = raw.get("rating")

    city = raw.get("city") or raw.get("locality") or raw.get("city_name") or fallback_city
    country_value = raw.get("country") or raw.get("country_code") or country

    normalized = {
        "company_name": company_name,
        "phone": str(phone).strip() if phone else None,
        "email": str(email).strip().lower() if email else None,
        "address": str(address).strip() if address else None,
        "website": str(website).strip() if website else None,
        "rating": float(rating) if rating not in (None, "") else None,
        "city": str(city).strip() if city else None,
        "country": str(country_value).strip() if country_value else country,
        "niche": niche,
        "source": source,
        "raw": raw,
    }

    return normalized


def _query_terms(niche: str, country: str, city: str | None) -> str:
    if city:
        return f"{niche} em {city}, {country}"
    return f"{niche} em {country}"


def _search_with_outscraper(niche: str, country: str, city: str | None, quantity: int) -> list[dict]:
    if not settings.outscraper_api_key:
        raise RuntimeError("OUTSCRAPER_API_KEY is not configured")

    client = OutscraperClient(api_key=settings.outscraper_api_key)
    query = _query_terms(niche, country, city)

    # Outscraper may return list[dict] or list[list[dict]] depending on SDK/runtime.
    response = client.google_maps_search(
        query=query,
        limit=max(quantity * 3, quantity),
        language="pt",
        region="br" if country.lower() in {"brasil", "brazil"} else None,
    )

    rows: list[dict] = []
    if isinstance(response, list):
        for item in response:
            if isinstance(item, dict):
                rows.append(item)
            elif isinstance(item, list):
                rows.extend([x for x in item if isinstance(x, dict)])

    if not rows:
        raise RuntimeError("Outscraper returned no rows")

    # Keep all valid unique results (don't cap at quantity) so per-user dedup
    # still has enough leads to reach the requested amount.
    normalized: list[dict] = []
    seen: set[str] = set()

    for row in rows:
        lead = _normalize_lead(row, niche=niche, country=country, fallback_city=city, source="outscraper")
        if not lead:
            continue
        key = _lead_hash(lead["company_name"], lead.get("city"), lead.get("phone"))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(lead)

    if not normalized:
        raise RuntimeError("Outscraper produced only invalid rows")

    return normalized


def _search_with_serpapi(niche: str, country: str, city: str | None, quantity: int) -> list[dict]:
    if not settings.serpapi_api_key:
        raise RuntimeError("SERPAPI_API_KEY is not configured")

    query = _query_terms(niche, country, city)
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "pt-BR",
        "api_key": settings.serpapi_api_key,
        "type": "search",
    }
    if country.lower() in {"brasil", "brazil"}:
        params["gl"] = "br"

    with httpx.Client(timeout=40.0) as client:
        response = client.get("https://serpapi.com/search.json", params=params)
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("local_results") or []
    if isinstance(rows, dict):
        rows = [rows]

    normalized: list[dict] = []
    seen: set[str] = set()

    for row in rows:
        lead = _normalize_lead(
            {
                "name": row.get("title") or row.get("name"),
                "phone": row.get("phone"),
                "website": row.get("website") or row.get("link"),
                "address": row.get("address"),
                "rating": row.get("rating"),
                "city": city,
                "country": country,
            },
            niche=niche,
            country=country,
            fallback_city=city,
            source="serpapi",
        )
        if not lead:
            continue
        key = _lead_hash(lead["company_name"], lead.get("city"), lead.get("phone"))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(lead)

    if not normalized:
        raise RuntimeError("SerpAPI returned no valid leads")

    return normalized


def search_businesses(
    niche: str,
    country: str = "Brasil",
    city: str | None = None,
    quantity: int = 5,
) -> list[dict]:
    niche = str(niche or "").strip()
    country = str(country or "Brasil").strip() or "Brasil"
    city = str(city).strip() if city else None
    quantity = _coerce_quantity(quantity)

    if not niche:
        raise RuntimeError("Niche is required")

    try:
        logger.info("Lead search started with Outscraper: niche=%s country=%s city=%s qty=%s", niche, country, city, quantity)
        return _search_with_outscraper(niche, country, city, quantity)
    except Exception as exc:
        logger.warning("Outscraper failed, falling back to SerpAPI: %s", exc)

    try:
        return _search_with_serpapi(niche, country, city, quantity)
    except Exception as exc:
        logger.error("SerpAPI fallback failed: %s", exc)
        raise RuntimeError("Lead providers failed (Outscraper and SerpAPI)") from exc


def collect_leads(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    if progress:
        progress(10, "Iniciando busca real de leads")

    leads = search_businesses(
        niche=request.nicho,
        country=request.pais,
        city=request.cidade,
        quantity=request.quantidade,
    )

    if progress:
        progress(90, f"{len(leads)} leads reais encontrados")

    if not leads:
        raise RuntimeError("Nenhum lead real foi retornado pelos provedores")

    if progress:
        progress(96, "Leads prontos para persistencia")

    return leads


def collect_workana(*args, **kwargs):  # pragma: no cover - legacy endpoint
    raise RuntimeError("Workana scraping was removed from this build")


def collect_services(*args, **kwargs):  # pragma: no cover - legacy endpoint
    raise RuntimeError("Services scraping was removed from this build")


def estimate_market_company_count(nicho: str, cidade: str, pais: str, sample_size: int = 30) -> int:
    leads = search_businesses(
        niche=nicho,
        country=pais,
        city=cidade,
        quantity=max(1, min(sample_size, 100)),
    )
    return len(leads)


