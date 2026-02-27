import asyncio
import random
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from utils import CircuitBreaker, add_observacao, clamp, random_delay, retry_async
from workana_scraper import WorkanaScraper

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

# Termos de busca por idioma (pessoa PROCURANDO contratar serviço)
SEARCH_TERMS = {
    "pt": [
        '"preciso de um site"',
        '"preciso de site"',
        '"preciso de landing page"',
        '"procuro desenvolvedor"',
        '"procuro programador"',
        '"procuro agência"',
        '"preciso de CRM"',
        '"preciso de sistema"',
        '"preciso de automação"',
        '"quero um site"',
        '"quero fazer um site"',
        '"contrato freelancer"',
        '"precisamos de agência"',
        '"preciso de social media"',
        '"preciso de web designer"',
        '"preciso de identidade visual"',
    ],
    "en": [
        '"need a website"',
        '"looking for web developer"',
        '"need a landing page"',
        '"need CRM system"',
        '"hire web developer"',
        '"looking for web designer"',
        '"need website built"',
        '"looking for agency"',
        '"need automation"',
        '"need internal system"',
    ],
}

LANG_MAP = {
    "Brasil": "pt",
    "Portugal": "pt",
    "Australia": "en",
}


class ProcuraServicoScraper:
    """Busca pessoas/empresas que estão PROCURANDO contratar serviços digitais."""

    def __init__(
        self,
        headless: bool = True,
        slowmo_ms: int = 0,
        proxy_manager=None,
        concurrency: int = 3,
    ) -> None:
        self.headless = headless
        self.slowmo_ms = slowmo_ms
        self.proxy_manager = proxy_manager
        self.concurrency = max(1, concurrency)
        self.workana = WorkanaScraper(
            headless=headless, slowmo_ms=slowmo_ms, proxy_manager=proxy_manager
        )
        self.breaker = CircuitBreaker()

    async def search_leads(
        self, pais: str, nicho: str, cidade: str | None, limite: int
    ) -> list[dict]:
        limite = clamp(limite, 1, 500)
        per_source = max(3, limite // 3)

        sem = asyncio.Semaphore(self.concurrency)

        async def _guard(coro):
            async with sem:
                return await coro

        lang = LANG_MAP.get(pais, "pt")
        terms = SEARCH_TERMS.get(lang, SEARCH_TERMS["pt"])
        random.shuffle(terms)
        query_batch = " OR ".join(terms[:6])

        tasks = [
            asyncio.create_task(
                _guard(self._search_google(pais, nicho, cidade, per_source, query_batch))
            ),
            asyncio.create_task(
                _guard(
                    self.workana.search_projects(nicho, per_source, pais, nicho, cidade)
                )
            ),
            asyncio.create_task(
                _guard(self._search_99freelas(pais, nicho, cidade, per_source))
            ),
            asyncio.create_task(
                _guard(self._search_google_site(pais, nicho, cidade, per_source))
            ),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        leads: list[dict] = []
        for item in results:
            if isinstance(item, Exception):
                print(f"  [procura] fonte com erro: {type(item).__name__}")
                continue
            leads += item

        print(f"  [procura] {len(leads)} oportunidades encontradas")
        return leads[:limite]

    # ------------------------------------------------------------------
    # Google Search (query genérica)
    # ------------------------------------------------------------------

    async def _search_google(
        self, pais, nicho, cidade, limite, query_batch
    ) -> list[dict]:
        query = f"({query_batch}) {cidade or ''} {pais}".strip()
        url = f"https://www.google.com/search?q={quote(query)}&num=20&hl=pt-BR"
        return await self._scrape_google_results(url, pais, nicho, cidade, limite, "google")

    # ------------------------------------------------------------------
    # Google site: (busca em redes sociais sem login)
    # ------------------------------------------------------------------

    async def _search_google_site(
        self, pais, nicho, cidade, limite
    ) -> list[dict]:
        lang = LANG_MAP.get(pais, "pt")
        if lang == "pt":
            terms = '"preciso de site" OR "procuro desenvolvedor" OR "preciso de sistema"'
        else:
            terms = '"need a website" OR "looking for developer" OR "need a system"'

        sites = "site:facebook.com OR site:reddit.com OR site:twitter.com"
        query = f"({terms}) ({sites}) {cidade or ''} {pais}".strip()
        url = f"https://www.google.com/search?q={quote(query)}&num=15&hl=pt-BR"
        return await self._scrape_google_results(url, pais, nicho, cidade, limite, "social-media")

    # ------------------------------------------------------------------
    # 99Freelas (plataforma brasileira de freelancers)
    # ------------------------------------------------------------------

    async def _search_99freelas(
        self, pais, nicho, cidade, limite
    ) -> list[dict]:
        if pais not in ("Brasil", "Todos"):
            return []

        search_terms = [
            "desenvolvimento site",
            "landing page",
            "sistema web",
            "CRM",
            "automação",
            "identidade visual",
            "web design",
        ]
        query = random.choice(search_terms)
        url = f"https://www.99freelas.com.br/projects?q={quote(query)}"
        leads: list[dict] = []

        async with async_playwright() as pw:
            browser = await self._launch(pw)
            page = await (await browser.new_context(locale="pt-BR", user_agent=UA)).new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(3000)

                cards = page.locator("li.result-container, div.project-item, article")
                total = min(await cards.count(), limite)

                for i in range(total):
                    try:
                        card = cards.nth(i)
                        titulo = (await card.locator("h1, h2, h3, a.title").first.inner_text()).strip()
                        link_el = card.locator("a").first
                        link = (await link_el.get_attribute("href") or "").strip()
                        if link and not link.startswith("http"):
                            link = f"https://www.99freelas.com.br{link}"

                        preco = ""
                        try:
                            preco = (await card.locator(".price, .budget, span[class*='price']").first.inner_text()).strip()
                        except Exception:
                            pass

                        lead = self._build_lead(
                            pais, nicho, cidade, titulo, link, "99freelas", preco=preco
                        )
                        leads.append(lead)
                    except Exception:
                        continue
            except Exception as e:
                print(f"  [99freelas] {type(e).__name__}")
            finally:
                await browser.close()

        return leads

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _launch(self, pw):
        proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
        return await pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            slow_mo=self.slowmo_ms,
            proxy=proxy,
        )

    async def _scrape_google_results(
        self, url, pais, nicho, cidade, limite, fonte
    ) -> list[dict]:
        leads: list[dict] = []

        async with async_playwright() as pw:
            browser = await self._launch(pw)
            page = await (await browser.new_context(locale="pt-BR", user_agent=UA)).new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(2500)
                await random_delay(min_s=1.5, max_s=3.5)

                results = page.locator("div.g")
                total = min(await results.count(), limite)
                print(f"  [{fonte}] {total} resultados Google")

                for i in range(total):
                    try:
                        item = results.nth(i)
                        title = (await item.locator("h3").first.inner_text()).strip()
                        link = await item.locator("a").first.get_attribute("href")
                        if not link:
                            continue

                        snippet = ""
                        try:
                            snippet = (await item.locator("div[data-sncf], div.VwiC3b, span.aCOpRe").first.inner_text()).strip()
                        except Exception:
                            pass

                        lead = self._build_lead(
                            pais, nicho, cidade, title, link, fonte, snippet=snippet
                        )
                        leads.append(lead)
                    except Exception:
                        continue
            except Exception as e:
                print(f"  [{fonte}] erro: {type(e).__name__}")
            finally:
                await browser.close()

        return leads

    def _build_lead(
        self,
        pais: str,
        nicho: str,
        cidade: str | None,
        titulo: str,
        link: str,
        fonte: str,
        preco: str = "",
        snippet: str = "",
    ) -> dict:
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        obs_parts = ["procura-servico", fonte, f"encontrado={now}"]
        if preco:
            obs_parts.append(f"preco={preco}")

        lead = {
            "pais": pais,
            "nicho": nicho,
            "nome_empresa": titulo or "Oportunidade",
            "cidade": cidade or "",
            "endereco": "",
            "telefone": "",
            "email": "",
            "instagram": "",
            "site": "",
            "linkedin": "",
            "fonte_link": link,
            "observacoes": ",".join(obs_parts),
        }
        if snippet:
            lead["descricao"] = snippet[:300]
        if preco:
            lead["preco"] = preco

        return lead

    async def _extract_post_time(self, item) -> str | None:
        try:
            time_el = item.locator("time")
            if await time_el.count() > 0:
                dt = await time_el.first.get_attribute("datetime")
                if dt:
                    return dt
                return (await time_el.first.inner_text()).strip() or None
        except Exception:
            return None
        return None
