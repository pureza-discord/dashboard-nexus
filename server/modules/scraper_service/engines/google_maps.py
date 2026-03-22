"""Google Maps scraper engine with dynamic domain routing."""

import logging
import re
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

from server.modules.scraper_service.core.utils import add_observacao

logger = logging.getLogger("scraper.google_maps")

# Dynamic Google domain map — route by country for local results.
# Fallback to google.com for unlisted countries.
GOOGLE_DOMAIN_MAP: dict[str, str] = {
    # Portuguese-speaking
    "brasil": "google.com.br",
    "brazil": "google.com.br",
    "portugal": "google.pt",
    "angola": "google.co.ao",
    "moçambique": "google.co.mz",
    "mozambique": "google.co.mz",
    # English-speaking
    "estados unidos": "google.com",
    "united states": "google.com",
    "usa": "google.com",
    "united kingdom": "google.co.uk",
    "uk": "google.co.uk",
    "reino unido": "google.co.uk",
    "australia": "google.com.au",
    "austrália": "google.com.au",
    "canada": "google.ca",
    "canadá": "google.ca",
    "india": "google.co.in",
    "new zealand": "google.co.nz",
    "ireland": "google.ie",
    "south africa": "google.co.za",
    # Spanish-speaking
    "españa": "google.es",
    "espanha": "google.es",
    "spain": "google.es",
    "mexico": "google.com.mx",
    "méxico": "google.com.mx",
    "argentina": "google.com.ar",
    "colombia": "google.com.co",
    "colômbia": "google.com.co",
    "chile": "google.cl",
    "peru": "google.com.pe",
    "uruguay": "google.com.uy",
    "paraguai": "google.com.py",
    "paraguay": "google.com.py",
    "venezuela": "google.co.ve",
    "bolivia": "google.com.bo",
    "equador": "google.com.ec",
    "ecuador": "google.com.ec",
    # European
    "france": "google.fr",
    "frança": "google.fr",
    "germany": "google.de",
    "alemanha": "google.de",
    "deutschland": "google.de",
    "italy": "google.it",
    "italia": "google.it",
    "itália": "google.it",
    "netherlands": "google.nl",
    "holanda": "google.nl",
    "belgium": "google.be",
    "switzerland": "google.ch",
    "suíça": "google.ch",
    "austria": "google.at",
    "poland": "google.pl",
    "polônia": "google.pl",
    "sweden": "google.se",
    "norway": "google.no",
    "denmark": "google.dk",
    "finland": "google.fi",
    "greece": "google.gr",
    "romania": "google.ro",
    "czech republic": "google.cz",
    "hungary": "google.hu",
    # Asian
    "japan": "google.co.jp",
    "japão": "google.co.jp",
    "south korea": "google.co.kr",
    "thailand": "google.co.th",
    "indonesia": "google.co.id",
    "philippines": "google.com.ph",
    "vietnam": "google.com.vn",
    "singapore": "google.com.sg",
    "malaysia": "google.com.my",
    "taiwan": "google.com.tw",
    # Middle East / Africa
    "israel": "google.co.il",
    "turkey": "google.com.tr",
    "turquia": "google.com.tr",
    "egypt": "google.com.eg",
    "nigeria": "google.com.ng",
    "kenya": "google.co.ke",
}

# Language hints per country for Google Maps hl parameter
LANG_MAP: dict[str, str] = {
    "brasil": "pt-BR",
    "brazil": "pt-BR",
    "portugal": "pt-PT",
    "estados unidos": "en",
    "united states": "en",
    "usa": "en",
    "united kingdom": "en",
    "uk": "en",
    "canada": "en",
    "canadá": "en",
    "australia": "en",
    "austrália": "en",
    "france": "fr",
    "frança": "fr",
    "germany": "de",
    "alemanha": "de",
    "italy": "it",
    "italia": "it",
    "itália": "it",
    "españa": "es",
    "espanha": "es",
    "spain": "es",
    "mexico": "es",
    "méxico": "es",
    "argentina": "es",
    "colombia": "es",
    "colômbia": "es",
    "chile": "es",
    "japan": "ja",
    "japão": "ja",
}


def _resolve_google_domain(pais: str) -> str:
    """Resolve the Google domain for a country. Fallback to google.com."""
    return GOOGLE_DOMAIN_MAP.get(pais.lower().strip(), "google.com")


def _resolve_lang(pais: str) -> str:
    """Resolve the hl language parameter. Fallback to en."""
    return LANG_MAP.get(pais.lower().strip(), "en")


class GoogleMapsEngine:
    """Google Maps lead scraper with dynamic domain routing.

    Uses country-specific Google domains (e.g. google.pt for Portugal,
    google.com for US). Real scrolling, pagination, and dedup.
    """

    FEED = 'div[role="feed"]'
    CARD = "a.hfpxzc"

    def __init__(
        self,
        headless: bool = True,
        slowmo_ms: int = 0,
        proxy_manager=None,
    ) -> None:
        self.headless = headless
        self.slowmo_ms = slowmo_ms
        self.proxy_manager = proxy_manager
        self.debug_dir = Path("debug_maps")
        self.debug_dir.mkdir(exist_ok=True)

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Scrape Google Maps for business leads.

        Args:
            query: Pre-built search query from query_builder.
            pais: Country (used for domain routing and lead tagging).
            nicho: Business niche (for lead tagging).
            cidade: City (for lead tagging, may be None).
            limite: Max number of leads to collect.

        Returns:
            List of raw lead dicts with fields: nome_empresa, telefone, site,
            email, cidade, endereco, pais, nicho, observacoes, etc.
        """
        domain = _resolve_google_domain(pais)
        lang = _resolve_lang(pais)
        url = f"https://www.{domain}/maps/search/{quote(query)}?hl={lang}"

        logger.info(
            "[SCRAPER] Google Maps | Domain: %s | Lang: %s | Query: %s",
            domain, lang, query,
        )

        leads: list[dict] = []
        async with async_playwright() as pw:
            browser = await self._launch(pw)
            try:
                leads = await self._run(browser, url, lang, pais, nicho, cidade, limite)
            finally:
                await browser.close()

        logger.info("[SCRAPER] Google Maps | Results: %d leads captured", len(leads))
        return leads

    async def _launch(self, pw: "async_playwright") -> "Browser":  # type: ignore[name-defined]
        proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
        return await pw.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
            slow_mo=self.slowmo_ms,
            proxy=proxy,
        )

    async def _run(self, browser: "Browser", url: str, lang: str, pais: str, nicho: str, cidade: str | None, limite: int) -> list[dict]:  # type: ignore[name-defined]
        ctx = await browser.new_context(
            locale=lang,
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        page = await ctx.new_page()

        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        logger.debug("[SCRAPER] Google Maps HTTP %s", resp.status if resp else "?")

        await self._accept_consent(page)
        await self._wait_for_feed(page)
        await page.screenshot(path=self.debug_dir / "01_loaded.png")

        await self._scroll_feed(page, limite)
        await page.screenshot(path=self.debug_dir / "02_scrolled.png")

        cards = page.locator(self.CARD)
        total: int = await cards.count()
        logger.debug("[SCRAPER] Google Maps | %d cards found", total)

        if total == 0:
            await self._dump_debug(page)
            return []

        leads: list[dict] = []
        seen_names: set[str] = set()

        for i in range(int(min(total, limite))):
            card = cards.nth(i)
            try:
                lead = await self._process_card(page, card, i, pais, nicho, cidade)
                if lead:
                    # Deduplicate by name within this batch
                    name_key = (lead.get("nome_empresa") or "").strip().lower()
                    if name_key and name_key in seen_names:
                        continue
                    seen_names.add(name_key)
                    leads.append(lead)
            except Exception as exc:
                logger.debug("[SCRAPER] Skip card %d: %s", i + 1, type(exc).__name__)

        return leads

    async def _accept_consent(self, page):
        for text in ("Aceitar tudo", "Accept all", "Concordo", "I agree",
                      "Aceptar todo", "Tout accepter", "Alle akzeptieren",
                      "Accetta tutto"):
            try:
                btn = page.get_by_role("button", name=re.compile(text, re.I))
                if await btn.count() > 0:
                    await btn.first.click(timeout=4000)
                    logger.debug("[SCRAPER] Google Maps consent accepted")
                    await page.wait_for_timeout(2000)
                    return
            except Exception:
                continue

    async def _wait_for_feed(self, page):
        try:
            await page.wait_for_selector(self.FEED, timeout=20_000)
            await page.wait_for_timeout(1500)
            return
        except Exception:
            pass

        try:
            await page.wait_for_selector(self.CARD, timeout=15_000)
            return
        except Exception:
            pass

        await page.wait_for_timeout(8000)

    async def _scroll_feed(self, page, limite: int):
        feed = page.locator(self.FEED)
        if await feed.count() == 0:
            await self._scroll_fallback(page, limite)
            return

        last = 0
        stale = 0

        for i in range(40):
            await feed.evaluate("el => el.scrollTop = el.scrollHeight")
            await page.wait_for_timeout(1200)

            now = await page.locator(self.CARD).count()
            if now >= limite:
                break

            if now == last:
                stale += 1
                if stale >= 5:
                    end = await page.locator(
                        'span.HlvSq, p.fontBodyMedium >> text=/final|end/'
                    ).count()
                    if end or stale >= 8:
                        break
            else:
                stale = 0
            last = now

    async def _scroll_fallback(self, page, limite: int):
        for _ in range(25):
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(1000)
            if await page.locator(self.CARD).count() >= limite:
                break

    async def _process_card(self, page: "Page", card: "Locator", idx: int, pais: str, nicho: str, cidade: str | None) -> dict | None:  # type: ignore[name-defined]
        await card.scroll_into_view_if_needed()
        await page.wait_for_timeout(600)
        await card.click(timeout=8000)
        await page.wait_for_timeout(2500)

        nome = await self._text(page, "h1.DUwDvf")
        if not nome:
            nome = (await card.get_attribute("aria-label") or "").strip()
        if not nome:
            return None

        endereco = await self._text(page, 'button[data-item-id="address"] .Io6YTe')
        if not endereco:
            endereco = await self._text(page, 'button[data-item-id="address"]')

        telefone = await self._text(page, 'button[data-item-id^="phone"] .Io6YTe')
        if not telefone:
            telefone = await self._text(page, 'button[data-item-id^="phone"]')

        site = ""
        try:
            a = page.locator('a[data-item-id="authority"]').first
            if await a.count():
                site = await a.get_attribute("href") or ""
        except Exception:
            pass

        rating = await self._text(page, "span.ceNzKf")
        if not rating:
            rating = await self._text(page, "span.fontDisplayLarge")

        reviews_raw = await self._text(page, 'span[aria-label*="coment"]')
        if not reviews_raw:
            reviews_raw = await self._text(page, 'span[aria-label*="review"]')
        reviews = self._parse_number(reviews_raw)

        coords = self._extract_coords(page.url)

        lead = {
            "pais": pais,
            "nicho": nicho,
            "nome_empresa": nome,
            "cidade": cidade or "",
            "endereco": endereco,
            "telefone": telefone,
            "email": "",
            "instagram": "",
            "site": site,
            "linkedin": "",
            "fonte_link": page.url,
            "observacoes": "",
            "rating": rating,
            "reviews_count": reviews,
            "coordinates": coords,
        }

        if site:
            add_observacao(lead, "tem_site")
        if telefone:
            add_observacao(lead, "tem_telefone")
        if rating:
            add_observacao(lead, "tem_rating")

        return lead

    async def _text(self, page, selector: str) -> str:
        try:
            el = page.locator(selector).first
            if await el.count() > 0 and await el.is_visible():
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _parse_number(text: str) -> str:
        if not text:
            return ""
        m = re.search(r"(\d[\d\.,]*)", text.replace("(", "").replace(")", ""))
        return m.group(1) if m else ""

    @staticmethod
    def _extract_coords(url: str) -> str:
        m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url or "")
        return f"{m.group(1)},{m.group(2)}" if m else ""

    async def _dump_debug(self, page):
        logger.warning("[SCRAPER] Google Maps: ZERO CARDS — dumping debug")
        await page.screenshot(path=self.debug_dir / "00_zero.png", full_page=True)
        with open(self.debug_dir / "00_zero.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
