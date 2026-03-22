"""Facebook page lead scraper engine — Google Search proxy approach.

Instead of directly scraping Facebook (which violates their ToS),
this engine searches Google for Facebook business pages matching
the target niche and location.

The Google search query: site:facebook.com "{niche}" "{city}"
"""

import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper.facebook")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]


class FacebookEngine:
    """Scrape Facebook business pages via Google Search proxy.

    Finds Facebook business pages by searching Google for
    `site:facebook.com "{niche}" "{location}"`.
    Extracts page names, URLs, and descriptions from results.
    """

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
        timeout: int = 15,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout = timeout

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Search for Facebook business pages via Google.

        Args:
            query: Search query string.
            pais: Country.
            nicho: Business niche.
            cidade: City (optional).
            limite: Max results.

        Returns:
            List of raw lead dicts with Facebook URLs.
        """
        import asyncio
        import random

        # Build Google search query targeting Facebook business pages
        location_part = f'"{cidade}"' if cidade else f'"{pais}"'
        google_query = f'site:facebook.com "{nicho}" {location_part}'

        leads: list[dict] = []
        seen_urls: set[str] = set()
        pages_to_fetch = min((limite // 10) + 1, 3)  # Max 3 pages

        logger.info(
            "[SCRAPER] Facebook (via Google) | Query: %s | Limit: %d",
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
                        logger.warning("[SCRAPER] Facebook Google search rate-limited")
                        break
                    if resp.status_code != 200:
                        continue

                    page_leads = self._parse_results(resp.text, pais, nicho, cidade, seen_urls)
                    leads.extend(page_leads)

                    if page_idx < pages_to_fetch - 1:
                        await asyncio.sleep(random.uniform(2.0, 4.0))

                except httpx.TimeoutException:
                    logger.warning("[SCRAPER] Facebook Google search timeout")
                    break
                except Exception as exc:
                    logger.error("[SCRAPER] Facebook error: %s", exc)
                    break

        logger.info("[SCRAPER] Facebook | Results: %d leads captured", len(leads))
        return list(leads[:limite])  # type: ignore

    def _parse_results(
        self,
        html: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        seen_urls: set[str],
    ) -> list[dict]:
        """Parse Google search results for Facebook business pages."""
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
                if not url or "facebook.com" not in url:
                    continue

                # Normalize Facebook URL
                fb_url = self._normalize_facebook_url(url)
                if not fb_url or fb_url in seen_urls:
                    continue

                # Skip profile pages, groups, events, etc.
                if any(skip in fb_url for skip in ["/groups/", "/events/", "/profile.php", "/people/"]):
                    continue

                seen_urls.add(fb_url)

                # Extract page name from title
                title_el = result.select_one("h3")
                title = title_el.get_text(strip=True) if title_el else ""
                # Clean Facebook suffix from title
                page_name = re.sub(r"\s*[|·-]\s*Facebook.*$", "", title, flags=re.I).strip()
                if not page_name:
                    continue

                # Extract snippet
                snippet_el = result.select_one("div.VwiC3b, span.aCOpRe")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # Try to extract phone from snippet
                phone = self._extract_phone(snippet)

                lead = {
                    "pais": pais,
                    "nicho": nicho,
                    "nome_empresa": page_name,
                    "cidade": cidade or "",
                    "endereco": "",
                    "telefone": phone,
                    "email": "",
                    "instagram": "",
                    "site": "",
                    "linkedin": "",
                    "facebook": fb_url,
                    "fonte_link": fb_url,
                    "observacoes": "via_facebook",
                }
                leads.append(lead)

            except Exception:
                continue

        return leads

    @staticmethod
    def _normalize_facebook_url(url: str) -> str:
        """Extract and normalize Facebook page URL."""
        m = re.search(r"(https?://(?:www\.)?facebook\.com/[^/?&#]+)", url)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_phone(text: str) -> str:
        """Try to extract a phone number from text."""
        if not text:
            return ""
        patterns = [
            r"\+?\d{1,3}[\s.-]?\(?\d{2,3}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,4}",
            r"\(\d{2,3}\)\s*\d{4,5}-?\d{4}",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(0).strip()
        return ""
