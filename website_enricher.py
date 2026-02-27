import asyncio
import json
import random
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from tqdm import tqdm

from utils import CircuitBreaker, add_observacao, random_delay, retry_async


EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(r"\+?\d{10,14}")
BR_MOBILE_REGEX = re.compile(r"\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}")

SOCIAL_DOMAINS = {
    "instagram": "instagram.com",
    "linkedin": "linkedin.com",
    "facebook": "facebook.com",
    "tiktok": "tiktok.com",
    "youtube": "youtube.com",
}

CONTACT_LINK_KEYWORDS = [
    "contato",
    "fale conosco",
    "fale com",
    "sobre",
    "quem somos",
    "agendar",
    "orcamento",
]

CONTACT_ACTION_KEYWORDS = [
    "agendar",
    "fale conosco",
    "fale com",
    "contato",
    "orcamento",
    "whatsapp",
    "marcar horario",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
]


class WebsiteEnricher:
    """Enriquecimento premium: emails, redes sociais, formularios e sinais de anuncio."""

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
        self.breaker = CircuitBreaker()

    async def enrich_leads(self, leads: list[dict]) -> list[dict]:
        sem = asyncio.Semaphore(self.concurrency)

        async def _guard(lead: dict) -> dict:
            async with sem:
                return await self._enrich_single(lead)

        tasks = [asyncio.create_task(_guard(lead)) for lead in leads]
        results: list[dict] = []

        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Enriquecendo", ncols=90):
            try:
                results.append(await coro)
            except Exception:
                continue

        return results

    async def _enrich_single(self, lead: dict) -> dict:
        site = lead.get("site")
        if not site:
            return lead

        try:
            data = await self._enrich_site(site)
        except Exception:
            return lead

        if data.get("emails") and not lead.get("email"):
            lead["email"] = data["emails"][0]
            add_observacao(lead, "tem_email")

        for rede in ["instagram", "linkedin", "facebook", "tiktok", "youtube"]:
            if data.get(rede) and not lead.get(rede):
                lead[rede] = data[rede]

        if data.get("whatsapp"):
            add_observacao(lead, "tem_wa")
        if data.get("whatsapp_business"):
            add_observacao(lead, "wa_business")

        if data.get("tem_formulario"):
            add_observacao(lead, "tem_formulario_contato")

        if data.get("anuncio_ativo"):
            add_observacao(lead, "anuncio-ativo")

        if data.get("schema_owner"):
            lead["schema_owner"] = data["schema_owner"]
        if data.get("owner_linkedin"):
            lead["owner_linkedin"] = data["owner_linkedin"]

        await random_delay(min_s=1.8, max_s=6)
        return lead

    async def _enrich_site(self, url: str) -> dict:
        async with async_playwright() as p:
            proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox"],
                slow_mo=self.slowmo_ms,
                proxy=proxy,
            )
            context = await browser.new_context(
                locale="pt-BR",
                user_agent=random.choice(USER_AGENTS),
            )
            page = await context.new_page()
            await stealth_async(page)

            async def _goto(target_url: str):
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            await retry_async(lambda: _goto(url), breaker=self.breaker)
            await page.wait_for_timeout(2000)

            html = await page.content()
            base_url = page.url

            # Tenta visitar paginas de contato/sobre
            extra_html = []
            for link in self._find_contact_links(html, base_url)[:2]:
                try:
                    await retry_async(lambda: _goto(link), breaker=self.breaker)
                    await page.wait_for_timeout(1500)
                    extra_html.append(await page.content())
                except Exception:
                    continue

            await browser.close()

        all_html = "\n".join([html] + extra_html)
        soup = BeautifulSoup(all_html, "lxml")

        emails = list({e.lower() for e in EMAIL_REGEX.findall(all_html)})
        emails += self._emails_from_mailto(soup)
        emails += self._emails_from_schema(all_html)
        emails = list(dict.fromkeys(emails))

        socials = self._extract_socials(soup)
        whatsapp = self._extract_whatsapp(all_html, soup)
        wa_business = self._detect_whatsapp_business(all_html)

        tem_formulario = self._detect_contact_form(soup)
        anuncio_ativo = self._detect_ads(all_html)
        schema_owner = self._extract_schema_owner(all_html)
        owner_linkedin = self._extract_owner_linkedin(soup)

        return {
            "emails": emails,
            "instagram": socials.get("instagram"),
            "linkedin": socials.get("linkedin"),
            "facebook": socials.get("facebook"),
            "tiktok": socials.get("tiktok"),
            "youtube": socials.get("youtube"),
            "whatsapp": whatsapp,
            "whatsapp_business": wa_business,
            "tem_formulario": tem_formulario,
            "anuncio_ativo": anuncio_ativo,
            "schema_owner": schema_owner,
            "owner_linkedin": owner_linkedin,
        }

    def _find_contact_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ").lower().strip()
            href = a["href"].strip()
            if not href or href.startswith("#"):
                continue
            if any(k in text for k in CONTACT_LINK_KEYWORDS):
                full = urljoin(base_url, href)
                if self._is_same_domain(full, base_url):
                    links.append(full)
        return list(dict.fromkeys(links))

    def _is_same_domain(self, url: str, base_url: str) -> bool:
        try:
            return urlparse(url).netloc == urlparse(base_url).netloc
        except Exception:
            return False

    def _emails_from_mailto(self, soup: BeautifulSoup) -> list[str]:
        emails: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0]
                if email:
                    emails.append(email.lower())
        return emails

    def _emails_from_schema(self, html: str) -> list[str]:
        emails: list[str] = []
        scripts = re.findall(r"<script type=\"application/ld\+json\">(.*?)</script>", html, re.S)
        for raw in scripts:
            try:
                data = json.loads(raw)
            except Exception:
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                email = item.get("email")
                if email:
                    emails.append(str(email).lower())
        return emails

    def _extract_socials(self, soup: BeautifulSoup) -> dict:
        found = {k: "" for k in SOCIAL_DOMAINS}
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            href_low = href.lower()
            for name, domain in SOCIAL_DOMAINS.items():
                if domain in href_low and not found[name]:
                    if self._validate_social(name, href_low):
                        found[name] = href
        return found

    def _validate_social(self, name: str, href_low: str) -> bool:
        if name == "instagram":
            return "/p/" not in href_low and href_low.count("/") >= 3
        if name == "linkedin":
            return "/company/" in href_low or "/in/" in href_low
        if name == "facebook":
            return "sharer.php" not in href_low
        if name == "tiktok":
            return "/@" in href_low
        if name == "youtube":
            return "/channel/" in href_low or "/@" in href_low
        return True

    def _extract_whatsapp(self, html: str, soup: BeautifulSoup) -> str:
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "wa.me" in href or "api.whatsapp.com" in href or "whatsapp" in href:
                return a["href"]

        br_numbers = BR_MOBILE_REGEX.findall(html)
        if br_numbers:
            return br_numbers[0]

        numbers = PHONE_REGEX.findall(html)
        return numbers[0] if numbers else ""

    def _detect_contact_form(self, soup: BeautifulSoup) -> bool:
        if soup.find("form"):
            return True

        if soup.find("input", {"type": "email"}):
            return True
        if soup.find("textarea"):
            return True

        text = " ".join([t.get_text(" ") for t in soup.find_all(["button", "a"])])
        text_low = text.lower()
        return any(k in text_low for k in CONTACT_ACTION_KEYWORDS)

    def _detect_ads(self, html: str) -> bool:
        html_low = html.lower()
        return any(
            tag in html_low
            for tag in ["adsbygoogle", "doubleclick", "googlesyndication", "adservice"]
        )

    def _extract_schema_owner(self, html: str) -> str:
        try:
            scripts = re.findall(r"<script type=\"application/ld\+json\">(.*?)</script>", html, re.S)
            for raw in scripts:
                data = json.loads(raw)
                if isinstance(data, list):
                    for item in data:
                        owner = self._extract_schema_name(item)
                        if owner:
                            return owner
                elif isinstance(data, dict):
                    owner = self._extract_schema_name(data)
                    if owner:
                        return owner
        except Exception:
            return ""
        return ""

    def _extract_owner_linkedin(self, soup: BeautifulSoup) -> str:
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "linkedin.com/in/" in href:
                return a["href"]
        return ""

    def _detect_whatsapp_business(self, html: str) -> bool:
        html_low = html.lower()
        return "whatsapp business" in html_low or "business.whatsapp.com" in html_low

    def _extract_schema_name(self, data: dict[str, Any]) -> str:
        for key in ["founder", "owner", "author", "creator"]:
            if key in data and isinstance(data[key], dict):
                return data[key].get("name", "")
        return data.get("name", "") if data.get("@type") in {"Person", "Organization"} else ""
