"""Unified scraper service with dynamic engine routing.

Entry point: search_leads() routes to the appropriate engine based on source.
Pluggable design — add new engines (LinkedIn, Yelp, etc.) without modifying core.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Literal

from server.core.settings import get_settings
from server.modules.scraper_service.core.geo_resolver import validate_geo
from server.modules.scraper_service.core.normalizer import deduplicate, normalize_leads
from server.modules.scraper_service.core.query_builder import build_google_maps_query, build_workana_query

settings = get_settings()
logger = logging.getLogger("scraper")

Source = Literal["google_maps", "workana", "linkedin", "facebook"]

ProgressCallback = Callable[[int, str], None]


@dataclass(slots=True)
class ScrapeRequest:
    nicho: str
    cidade: str | None
    pais: str
    quantidade: int
    source: Source = "google_maps"


def search_leads(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    """Unified entry point. Routes to the correct engine by source.

    Validates geo strictly. Deduplicates by name+phone.
    Credit logic: this function raises on failure — caller should only
    decrement credits after successful return.
    """
    nicho = (request.nicho or "").strip()
    pais = (request.pais or "").strip()
    quantidade = max(1, min(int(request.quantidade or 1), 1000))

    if not nicho:
        raise ValueError("Niche (nicho) is required for scraping.")
    if not pais:
        raise ValueError("Country (pais) is required for scraping. No default will be assumed.")

    # Strict geo validation — raises GeoValidationError on mismatch
    pais, cidade = validate_geo(pais, request.cidade)

    logger.info(
        "[SCRAPER] Request | Niche: %s | Country: %s | City: %s | Qty: %d | Engine: %s",
        nicho, pais, cidade, quantidade, request.source,
    )

    sanitized = ScrapeRequest(
        nicho=nicho,
        cidade=cidade,
        pais=pais,
        quantidade=quantidade,
        source=request.source,
    )

    if request.source == "workana":
        return _run_workana(sanitized, progress)

    if request.source == "linkedin":
        return _run_linkedin(sanitized, progress)

    if request.source == "facebook":
        return _run_facebook(sanitized, progress)

    # Default: google_maps
    if settings.scraper_mode == "google_maps":
        return _run_google_maps(sanitized, progress)

    return _generate_mock_leads(sanitized, progress)


# --------------------------------------------------------------------------
# Backward-compatible alias used by tasks.py
# --------------------------------------------------------------------------
def collect_leads(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    """Backward-compatible alias for search_leads."""
    return search_leads(request, progress)


# --------------------------------------------------------------------------
# Google Maps engine
# --------------------------------------------------------------------------
def _run_google_maps(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    try:
        return asyncio.run(_run_google_maps_async(request, progress))
    except Exception as exc:
        raise RuntimeError(f"Google Maps scraping failed: {exc}") from exc


async def _run_google_maps_async(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    from server.modules.scraper_service.engines.google_maps import GoogleMapsEngine
    from website_enricher import WebsiteEnricher

    if progress:
        progress(10, "Initializing browser for scraping")

    query = build_google_maps_query(request.nicho, request.cidade, request.pais)
    engine = GoogleMapsEngine(headless=True, slowmo_ms=0)
    raw_leads = await engine.search_leads(
        query=query,
        pais=request.pais,
        nicho=request.nicho,
        cidade=request.cidade,
        limite=request.quantidade,
    )

    if not raw_leads:
        raise RuntimeError("Google Maps returned zero results for the given filters")

    if progress:
        progress(68, "Enriching contact data")

    enricher = WebsiteEnricher(headless=True, slowmo_ms=0, concurrency=3)
    enriched = await enricher.enrich_leads(raw_leads)

    normalized = normalize_leads(
        enriched[:request.quantidade],
        nicho=request.nicho,
        pais=request.pais,
        cidade=request.cidade,
        source="google_maps",
    )

    # Deduplicate by name + phone
    normalized = deduplicate(normalized)

    real_count = len([l for l in normalized if (l.get("empresa") or "").strip()])
    if real_count == 0:
        raise RuntimeError("Scraping completed with zero valid leads")

    logger.info(
        "[SCRAPER] Google Maps | Niche: %s | Country: %s | City: %s | Qty: %d | Results: %d",
        request.nicho, request.pais, request.cidade, request.quantidade, len(normalized),
    )

    if progress:
        progress(95, "Real leads collected successfully")

    return normalized


# --------------------------------------------------------------------------
# Workana engine
# --------------------------------------------------------------------------
def _run_workana(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    try:
        return asyncio.run(_run_workana_async(request, progress))
    except Exception as exc:
        raise RuntimeError(f"Workana scraping failed: {exc}") from exc


async def _run_workana_async(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    from server.modules.scraper_service.engines.workana import WorkanaEngine

    if progress:
        progress(10, "Initializing Workana search")

    query = build_workana_query(request.nicho, request.pais)
    engine = WorkanaEngine(headless=True, slowmo_ms=0)
    raw_leads = await engine.search_leads(
        query=query,
        pais=request.pais,
        nicho=request.nicho,
        cidade=request.cidade,
        limite=request.quantidade,
    )

    normalized = normalize_leads(
        raw_leads[:request.quantidade],
        nicho=request.nicho,
        pais=request.pais,
        cidade=request.cidade,
        source="workana",
    )

    normalized = deduplicate(normalized)

    logger.info(
        "[SCRAPER] Workana | Niche: %s | Country: %s | City: %s | Qty: %d | Results: %d",
        request.nicho, request.pais, request.cidade, request.quantidade, len(normalized),
    )

    if progress:
        progress(95, "Workana leads collected successfully")

    return normalized


# --------------------------------------------------------------------------
# Mock engine (dev/testing only)
# --------------------------------------------------------------------------
def _generate_mock_leads(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    import random
    import time

    if progress:
        progress(10, "Initializing mock search")

    nicho = request.nicho
    cidade = request.cidade
    pais = request.pais
    quantidade = request.quantidade

    prefixes = [
        "Group", "Institute", "Center", "Clinic", "Office", "Agency",
        "Consulting", "Network", "Studio", "Hub", "Lab", "House",
    ]
    surnames = [
        "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa",
        "Rodrigues", "Almeida", "Lima", "Fernandes", "Carvalho", "Gomes",
    ]

    leads: list[dict] = []
    used_names: set[str] = set()

    if progress:
        progress(25, f"Searching {nicho} in {cidade or pais}")

    for i in range(quantidade):
        prefix = random.choice(prefixes)
        surname = random.choice(surnames)
        suffix = random.randint(1, 999)
        empresa = f"{prefix} {surname} {nicho.title()}"

        attempt = 0
        while empresa in used_names and attempt < 20:
            empresa = f"{prefix} {surname} {nicho.title()} {suffix}"
            suffix = random.randint(1, 9999)
            attempt += 1
        used_names.add(empresa)

        slug = empresa.lower().replace(" ", "").replace(".", "")[:12]
        has_phone = random.random() > 0.15
        has_email = random.random() > 0.2
        has_site = random.random() > 0.4

        phone = f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}" if has_phone else None
        email = f"contact@{slug}.com" if has_email else None
        site = f"https://www.{slug}.com" if has_site else None

        leads.append({
            "empresa": empresa,
            "telefone": phone,
            "email": email,
            "site": site,
            "cidade": cidade or "National",
            "pais": pais,
            "nicho": nicho,
            "origem": "mock_scraper",
            "observacoes": "",
        })

        if progress and (i + 1) % max(1, quantidade // 4) == 0:
            pct = 25 + int((i / quantidade) * 65)
            progress(min(pct, 90), f"Collected {i + 1}/{quantidade} leads")

    time.sleep(0.5)

    logger.info(
        "[SCRAPER] Mock | Niche: %s | Country: %s | City: %s | Qty: %d | Results: %d",
        nicho, pais, cidade, quantidade, len(leads),
    )

    if progress:
        progress(95, f"{len(leads)} mock leads generated")

    return leads


# --------------------------------------------------------------------------
# LinkedIn engine
# --------------------------------------------------------------------------
def _run_linkedin(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    try:
        return asyncio.run(_run_linkedin_async(request, progress))
    except Exception as exc:
        raise RuntimeError(f"LinkedIn scraping failed: {exc}") from exc


async def _run_linkedin_async(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    import os
    from server.modules.scraper_service.engines.linkedin import LinkedInEngine

    if progress:
        progress(10, "Connecting to LinkedIn API")

    api_key = os.getenv("LINKEDIN_API_KEY", "")
    engine = LinkedInEngine(api_key=api_key or None)
    query = f"{request.nicho} {request.cidade or ''} {request.pais}".strip()
    raw_leads = await engine.search_leads(
        query=query,
        pais=request.pais,
        nicho=request.nicho,
        cidade=request.cidade,
        limite=request.quantidade,
    )

    if not raw_leads:
        raise RuntimeError(
            "LinkedIn returned zero results. Ensure LINKEDIN_API_KEY is configured."
        )

    if progress:
        progress(80, "Normalizing LinkedIn results")

    normalized = normalize_leads(
        raw_leads, nicho=request.nicho, pais=request.pais,
        cidade=request.cidade, source="linkedin",
    )
    return deduplicate(normalized)


# --------------------------------------------------------------------------
# Facebook engine
# --------------------------------------------------------------------------
def _run_facebook(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    try:
        return asyncio.run(_run_facebook_async(request, progress))
    except Exception as exc:
        raise RuntimeError(f"Facebook scraping failed: {exc}") from exc


async def _run_facebook_async(request: ScrapeRequest, progress: ProgressCallback | None) -> list[dict]:
    import os
    from server.modules.scraper_service.engines.facebook import FacebookEngine

    if progress:
        progress(10, "Connecting to Facebook Graph API")

    app_id = os.getenv("FACEBOOK_APP_ID", "")
    app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
    engine = FacebookEngine(app_id=app_id or None, app_secret=app_secret or None)
    query = f"{request.nicho} {request.cidade or ''} {request.pais}".strip()
    raw_leads = await engine.search_leads(
        query=query,
        pais=request.pais,
        nicho=request.nicho,
        cidade=request.cidade,
        limite=request.quantidade,
    )

    if not raw_leads:
        raise RuntimeError(
            "Facebook returned zero results. Ensure FACEBOOK_APP_ID is configured."
        )

    if progress:
        progress(80, "Normalizing Facebook results")

    normalized = normalize_leads(
        raw_leads, nicho=request.nicho, pais=request.pais,
        cidade=request.cidade, source="facebook",
    )
    return deduplicate(normalized)


# --------------------------------------------------------------------------
# Market estimation (used by market intelligence service)
# --------------------------------------------------------------------------
def estimate_market_company_count(nicho: str, cidade: str, pais: str, sample_size: int = 120) -> int:
    """Estimate the number of companies in a market by sampling."""
    nicho = (nicho or "").strip()
    pais = (pais or "").strip()
    cidade = (cidade or "").strip() or None

    if not nicho:
        raise ValueError("Niche is required for market estimation.")
    if not pais:
        raise ValueError("Country is required for market estimation.")

    sampled = search_leads(
        ScrapeRequest(
            nicho=nicho,
            cidade=cidade,
            pais=pais,
            quantidade=max(10, min(sample_size, 200)),
        )
    )
    return len(sampled)

