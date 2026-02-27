from urllib.parse import quote

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from utils import CircuitBreaker, add_observacao, clamp, random_delay, retry_async


class WorkanaScraper:
    """Busca projetos abertos no Workana (best-effort)."""

    def __init__(self, headless: bool = True, slowmo_ms: int = 0, proxy_manager=None) -> None:
        self.headless = headless
        self.slowmo_ms = slowmo_ms
        self.proxy_manager = proxy_manager
        self.breaker = CircuitBreaker()

    async def search_projects(
        self,
        query: str,
        limite: int,
        pais: str,
        nicho: str,
        cidade: str | None,
    ) -> list[dict]:
        limite = clamp(limite, 1, 200)
        query_text = query
        if pais:
            query_text = f"{query} {pais}"
        url = f"https://www.workana.com/jobs?query={quote(query_text)}&status=published"
        leads: list[dict] = []

        async with async_playwright() as p:
            proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox"],
                slow_mo=self.slowmo_ms,
                proxy=proxy,
            )
            context = await browser.new_context(locale="pt-BR")
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
                            "nome_empresa": titulo or "Projeto Workana",
                            "cidade": cidade or "",
                            "endereco": "",
                            "telefone": "",
                            "email": "",
                            "instagram": "",
                            "site": "",
                            "linkedin": "",
                            "fonte_link": link,
                            "observacoes": "procura-servico",
                        }
                        add_observacao(lead, "workana")
                        leads.append(lead)
                    except Exception:
                        continue
            except PlaywrightTimeoutError:
                pass
            finally:
                await browser.close()

        return leads
