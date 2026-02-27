import re
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

from utils import add_observacao


class GoogleMapsScraper:
    """Google Maps lead scraper. Requer WebGL ativo (NÃO usar --disable-gpu)."""

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

    # ------------------------------------------------------------------
    # Público
    # ------------------------------------------------------------------

    async def search_leads(
        self,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
        geo=None,
        raio_km=None,
    ) -> list[dict]:
        query = f"{nicho} {cidade or ''} {pais}".strip()
        url = f"https://www.google.com/maps/search/{quote(query)}?hl=pt-BR"
        print(f"[Maps] Buscando: {query}")

        async with async_playwright() as pw:
            browser = await self._launch(pw)
            try:
                leads = await self._run(browser, url, pais, nicho, cidade, limite)
            finally:
                await browser.close()

        print(f"[Maps] {len(leads)} leads capturados")
        return leads

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    async def _launch(self, pw):
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

    async def _run(self, browser, url, pais, nicho, cidade, limite):
        ctx = await browser.new_context(
            locale="pt-BR",
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
        print(f"[Maps] HTTP {resp.status if resp else '?'}")

        await self._accept_consent(page)
        await self._wait_for_feed(page)
        await page.screenshot(path=self.debug_dir / "01_loaded.png")

        await self._scroll_feed(page, limite)
        await page.screenshot(path=self.debug_dir / "02_scrolled.png")

        cards = page.locator(self.CARD)
        total = await cards.count()
        print(f"[Maps] {total} cards encontrados")

        if total == 0:
            await self._dump_debug(page)
            return []

        leads: list[dict] = []
        for i in range(min(total, limite)):
            card = cards.nth(i)
            try:
                lead = await self._process_card(page, card, i, pais, nicho, cidade)
                if lead:
                    leads.append(lead)
                    print(f"  {len(leads)}. {lead['nome_empresa'][:55]}")
            except Exception as exc:
                print(f"  [skip card {i+1}] {type(exc).__name__}")

        return leads

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    async def _accept_consent(self, page):
        for text in ("Aceitar tudo", "Accept all", "Concordo", "I agree"):
            try:
                btn = page.get_by_role("button", name=re.compile(text, re.I))
                if await btn.count() > 0:
                    await btn.first.click(timeout=4000)
                    print("[Maps] Consent aceito")
                    await page.wait_for_timeout(2000)
                    return
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Espera o feed carregar
    # ------------------------------------------------------------------

    async def _wait_for_feed(self, page):
        try:
            await page.wait_for_selector(self.FEED, timeout=20_000)
            print("[Maps] Feed pronto")
            await page.wait_for_timeout(1500)
            return
        except Exception:
            pass

        try:
            await page.wait_for_selector(self.CARD, timeout=15_000)
            print("[Maps] Cards visíveis")
            return
        except Exception:
            pass

        print("[Maps] Aguardando render extra (8s)...")
        await page.wait_for_timeout(8000)

    # ------------------------------------------------------------------
    # Scroll dentro do feed
    # ------------------------------------------------------------------

    async def _scroll_feed(self, page, limite: int):
        feed = page.locator(self.FEED)
        if await feed.count() == 0:
            print("[Maps] Feed nao encontrado, scroll fallback")
            await self._scroll_fallback(page, limite)
            return

        last = 0
        stale = 0

        for i in range(40):
            await feed.evaluate("el => el.scrollTop = el.scrollHeight")
            await page.wait_for_timeout(1200)

            now = await page.locator(self.CARD).count()
            if i % 5 == 0:
                print(f"  scroll {i+1}: {now} cards")

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
        for i in range(25):
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(1000)
            if await page.locator(self.CARD).count() >= limite:
                break

    # ------------------------------------------------------------------
    # Processar card individual
    # ------------------------------------------------------------------

    async def _process_card(self, page, card, idx, pais, nicho, cidade):
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        print("[Maps] ZERO CARDS - dump de diagnóstico")
        await page.screenshot(path=self.debug_dir / "00_zero.png", full_page=True)
        with open(self.debug_dir / "00_zero.html", "w", encoding="utf-8") as f:
            f.write(await page.content())

        for sel, name in [
            (self.FEED, "feed"),
            (self.CARD, "cards"),
            ("canvas", "canvas"),
            ("#searchboxinput", "searchbox"),
        ]:
            try:
                print(f"  {name}: {await page.locator(sel).count()}")
            except Exception:
                pass
