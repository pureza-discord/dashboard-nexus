"""Workana scraper engine. Dynamic keyword search — no fixed niches."""

import logging
from urllib.parse import quote

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from server.modules.scraper_service.core.utils import CircuitBreaker, add_observacao, clamp, random_delay, retry_async

logger = logging.getLogger("scraper.workana")


class WorkanaEngine:
    """Scrape job/project listings from Workana.

    Accepts any keyword (Dev, Design, Marketing, etc.). No fixed niche list.
    """

    def __init__(self, headless: bool = True, slowmo_ms: int = 0, proxy_manager=None) -> None:
        self.headless = headless
        self.slowmo_ms = slowmo_ms
        self.proxy_manager = proxy_manager
        self.breaker = CircuitBreaker()

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Search Workana for project listings matching the query.

        Args:
            query: Pre-built search query from query_builder.
            pais: Country (for lead tagging).
            nicho: Niche/keyword (for lead tagging).
            cidade: City (for lead tagging, may be None).
            limite: Max number of leads.

        Returns:
            List of raw lead dicts.
        """
        limite = clamp(limite, 1, 200)
        url = f"https://www.workana.com/jobs?query={quote(query)}&status=published"

        logger.info(
            "[SCRAPER] Workana | Query: %s | Limite: %d",
            query, limite,
        )

        leads: list[dict] = []

        async with async_playwright() as p:
            proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox"],
                slow_mo=self.slowmo_ms,
                proxy=proxy,
            )
            context = await browser.new_context(locale="en")
            page = await context.new_page()

            try:
                await retry_async(
                    lambda: page.goto(url, wait_until="domcontentloaded", timeout=60000),
                    breaker=self.breaker,
                )
                await page.wait_for_timeout(2000)
                await random_delay(min_s=1.8, max_s=4)

                cards = page.locator("article")
                total = min(await cards.count(), limite)

                for i in range(total):
                    card = cards.nth(i)
                    try:
                        titulo = (await card.locator("h2, h3").first.inner_text()).strip()
                        link = await card.locator("a").first.get_attribute("href")
                        link = (link or "").strip()
                        if link and link.startswith("/"):
                            link = f"https://www.workana.com{link}"

                        lead = {
                            "pais": pais,
                            "nicho": nicho,
                            "nome_empresa": titulo or "Workana Project",
                            "cidade": cidade or "",
                            "endereco": "",
                            "telefone": "",
                            "email": "",
                            "instagram": "",
                            "site": "",
                            "linkedin": "",
                            "fonte_link": link,
                            "observacoes": "",
                        }
                        add_observacao(lead, "procura-servico")
                        add_observacao(lead, "workana")
                        leads.append(lead)
                    except Exception:
                        continue
            except PlaywrightTimeoutError:
                logger.warning("[SCRAPER] Workana timeout for query: %s", query)
            finally:
                await browser.close()

        logger.info("[SCRAPER] Workana | Results: %d leads captured", len(leads))
        return leads
