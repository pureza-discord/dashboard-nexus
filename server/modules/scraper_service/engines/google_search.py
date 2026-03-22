"""Google Search scraper engine.

Scrapes business listings from Google search results for any niche/location.
Uses httpx + BeautifulSoup — no browser needed, fast and lightweight.
Falls back gracefully if rate-limited.
"""

import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper.google_search")

# User-Agent rotation for anti-detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]


class GoogleSearchEngine:
    """Scrape business leads from Google Search results.

    Lightweight alternative to Google Maps — no browser required.
    Extracts company names, websites, and snippets from organic results.
    """

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Search Google for business leads.

        Args:
            query: Search query string.
            pais: Country (for lead tagging).
            nicho: Business niche (for lead tagging).
            cidade: City (optional, for lead tagging).
            limite: Max results to collect.

        Returns:
            List of raw lead dicts.
        """
        import random

        leads: list[dict] = []
        seen_domains: set[str] = set()
        pages_to_fetch = min((limite // 10) + 1, 5)  # Max 5 pages

        logger.info(
            "[SCRAPER] Google Search | Query: %s | Pages: %d | Limit: %d",
            query, pages_to_fetch, limite,
        )

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7"},
        ) as client:
            for page_idx in range(pages_to_fetch):
                if len(leads) >= limite:
                    break

                start = page_idx * 10
                search_url = (
                    f"https://www.google.com/search"
                    f"?q={quote_plus(query)}"
                    f"&start={start}"
                    f"&num=10"
                )

                try:
                    ua = random.choice(USER_AGENTS)
                    resp = await client.get(
                        search_url,
                        headers={"User-Agent": ua},
                    )

                    if resp.status_code == 429:
                        logger.warning("[SCRAPER] Google Search rate-limited at page %d", page_idx + 1)
                        break

                    if resp.status_code != 200:
                        logger.warning("[SCRAPER] Google Search HTTP %d at page %d", resp.status_code, page_idx + 1)
                        continue

                    page_leads = self._parse_results(resp.text, pais, nicho, cidade, seen_domains)
                    leads.extend(page_leads)

                    # Small delay between pages
                    if page_idx < pages_to_fetch - 1:
                        import asyncio
                        await asyncio.sleep(random.uniform(1.5, 3.5))

                except httpx.TimeoutException:
                    logger.warning("[SCRAPER] Google Search timeout at page %d", page_idx + 1)
                    break
                except Exception as exc:
                    logger.error("[SCRAPER] Google Search error: %s", exc)
                    break

        logger.info("[SCRAPER] Google Search | Results: %d leads captured", len(leads))
        return list(leads[:limite])  # type: ignore

    def _parse_results(
        self,
        html: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        seen_domains: set[str],
    ) -> list[dict]:
        """Parse Google search results HTML into lead dicts."""
        soup = BeautifulSoup(html, "lxml")
        leads: list[dict] = []

        # Google organic results are in div.g
        results = soup.select("div.g")
        if not results:
            # Fallback: try broader selectors
            results = soup.select("div[data-sokoban-container]")

        for result in results:
            try:
                # Extract link
                link_el = result.select_one("a[href]")
                if not link_el:
                    continue
                href_attr = link_el.get("href", "")
                url = href_attr[0] if isinstance(href_attr, list) else href_attr
                if not url or not url.startswith("http"):
                    continue

                # Skip Google-internal pages, Wikipedia, social media
                domain = self._extract_domain(url)
                if not domain or domain in seen_domains:
                    continue
                skip_domains = {
                    "google.com", "youtube.com", "wikipedia.org",
                    "facebook.com", "twitter.com", "instagram.com",
                    "linkedin.com", "pinterest.com", "reddit.com",
                    "tiktok.com", "amazon.com", "yelp.com",
                }
                if any(domain.endswith(sd) for sd in skip_domains):
                    continue

                seen_domains.add(domain)

                # Extract title (company name proxy)
                title_el = result.select_one("h3")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # Extract snippet
                snippet_el = result.select_one("div.VwiC3b, span.aCOpRe, div[data-sncf]")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # Try to extract phone from snippet
                phone = self._extract_phone(snippet)

                # Try to extract email from snippet
                email = self._extract_email(snippet)

                lead = {
                    "pais": pais,
                    "nicho": nicho,
                    "nome_empresa": title,
                    "cidade": cidade or "",
                    "endereco": "",
                    "telefone": phone,
                    "email": email,
                    "instagram": "",
                    "site": url,
                    "linkedin": "",
                    "fonte_link": url,
                    "observacoes": "via_google_search",
                }
                leads.append(lead)

            except Exception:
                continue

        return leads

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract clean domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = (parsed.netloc or "").lower()
            domain = re.sub(r"^www\.", "", domain)
            return domain.split(":")[0]
        except Exception:
            return ""

    @staticmethod
    def _extract_phone(text: str) -> str:
        """Try to extract a phone number from text."""
        if not text:
            return ""
        # Match common phone patterns
        patterns = [
            r"\+?\d{1,3}[\s.-]?\(?\d{2,3}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,4}",
            r"\(\d{2,3}\)\s*\d{4,5}-?\d{4}",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(0).strip()
        return ""

    @staticmethod
    def _extract_email(text: str) -> str:
        """Try to extract an email from text."""
        if not text:
            return ""
        m = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        return m.group(0) if m else ""
