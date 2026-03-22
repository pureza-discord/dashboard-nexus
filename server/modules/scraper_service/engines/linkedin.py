"""LinkedIn lead scraper engine — Google Search proxy approach.

Instead of directly scraping LinkedIn (which violates their ToS),
this engine searches Google for LinkedIn company pages matching
the target niche and location. This is legal and effective.

The Google search query: site:linkedin.com/company "{niche}" "{city}"
"""

import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper.linkedin")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]


class LinkedInEngine:
    """Scrape LinkedIn company profiles via Google Search proxy.

    Finds LinkedIn company pages by searching Google for
    `site:linkedin.com/company "{niche}" "{location}"`.
    Extracts company name, LinkedIn URL, and description from results.
    """

    def __init__(self, api_key: str | None = None, timeout: int = 15) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Search for LinkedIn company pages via Google.

        Args:
            query: Search query string.
            pais: Country.
            nicho: Business niche.
            cidade: City (optional).
            limite: Max results.

        Returns:
            List of raw lead dicts with LinkedIn URLs.
        """
        import asyncio
        import random

        # Build a Google search query targeting LinkedIn company pages
        location_part = f'"{cidade}"' if cidade else f'"{pais}"'
        google_query = f'site:linkedin.com/company "{nicho}" {location_part}'

        leads: list[dict] = []
        seen_urls: set[str] = set()
        pages_to_fetch = min((limite // 10) + 1, 3)  # Max 3 pages

        logger.info(
            "[SCRAPER] LinkedIn (via Google) | Query: %s | Limit: %d",
            google_query, limite,
        )

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        ) as client:
            for page_idx in range(pages_to_fetch):
                if len(leads) >= limite:
                    break

                start = page_idx * 10
                search_url = (
                    f"https://www.google.com/search"
                    f"?q={quote_plus(google_query)}"
                    f"&start={start}&num=10"
                )

                try:
                    ua = random.choice(USER_AGENTS)
                    resp = await client.get(
                        search_url,
                        headers={"User-Agent": ua},
                    )

                    if resp.status_code == 429:
                        logger.warning("[SCRAPER] LinkedIn Google search rate-limited")
                        break
                    if resp.status_code != 200:
                        continue

                    page_leads = self._parse_results(resp.text, pais, nicho, cidade, seen_urls)
                    leads.extend(page_leads)

                    if page_idx < pages_to_fetch - 1:
                        await asyncio.sleep(random.uniform(2.0, 4.0))

                except httpx.TimeoutException:
                    logger.warning("[SCRAPER] LinkedIn Google search timeout")
                    break
                except Exception as exc:
                    logger.error("[SCRAPER] LinkedIn error: %s", exc)
                    break

        logger.info("[SCRAPER] LinkedIn | Results: %d leads captured", len(leads))
        return list(leads[:limite])  # type: ignore

    def _parse_results(
        self,
        html: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        seen_urls: set[str],
    ) -> list[dict]:
        """Parse Google search results for LinkedIn company pages."""
        soup = BeautifulSoup(html, "lxml")
        leads: list[dict] = []

        results = soup.select("div.g")
        for result in results:
            try:
                link_el = result.select_one("a[href]")
                if not link_el:
                    continue
                href_attr = link_el.get("href", "")
                url = href_attr[0] if isinstance(href_attr, list) else href_attr
                if not url or "linkedin.com/company" not in url:
                    continue

                # Normalize LinkedIn URL
                linkedin_url = self._normalize_linkedin_url(url)
                if not linkedin_url or linkedin_url in seen_urls:
                    continue
                seen_urls.add(linkedin_url)

                # Extract company name from title
                title_el = result.select_one("h3")
                title = title_el.get_text(strip=True) if title_el else ""
                # Clean LinkedIn suffix from title (e.g., "Company Name | LinkedIn")
                company_name = re.sub(r"\s*[|·-]\s*LinkedIn.*$", "", title, flags=re.I).strip()
                if not company_name:
                    continue

                # Extract description from snippet
                snippet_el = result.select_one("div.VwiC3b, span.aCOpRe")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                lead = {
                    "pais": pais,
                    "nicho": nicho,
                    "nome_empresa": company_name,
                    "cidade": cidade or "",
                    "endereco": "",
                    "telefone": "",
                    "email": "",
                    "instagram": "",
                    "site": "",
                    "linkedin": linkedin_url,
                    "fonte_link": linkedin_url,
                    "observacoes": "via_linkedin",
                }
                leads.append(lead)

            except Exception:
                continue

        return leads

    @staticmethod
    def _normalize_linkedin_url(url: str) -> str:
        """Extract and normalize LinkedIn company URL."""
        m = re.search(r"(https?://(?:www\.)?linkedin\.com/company/[^/?&#]+)", url)
        return m.group(1) if m else ""
