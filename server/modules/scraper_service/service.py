import asyncio
from dataclasses import dataclass
from typing import Callable

from server.core.settings import get_settings

settings = get_settings()


@dataclass(slots=True)
class ScrapeRequest:
    nicho: str
    cidade: str | None
    pais: str
    quantidade: int


ProgressCallback = Callable[[int, str], None]


async def _run_google_maps_async(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    from google_maps_scraper import GoogleMapsScraper
    from website_enricher import WebsiteEnricher

    if progress:
        progress(10, "Inicializando navegador para scraping")

    scraper = GoogleMapsScraper(headless=True, slowmo_ms=0)
    leads = await scraper.search_leads(
        pais=request.pais,
        nicho=request.nicho,
        cidade=request.cidade,
        limite=request.quantidade,
    )

    if not leads:
        raise RuntimeError("Google Maps retornou zero resultados para os filtros informados")

    if progress:
        progress(68, "Executando enriquecimento de contatos")

    enricher = WebsiteEnricher(headless=True, slowmo_ms=0, concurrency=3)
    enriched = await enricher.enrich_leads(leads)

    normalized: list[dict] = []
    for item in enriched[: request.quantidade]:
        normalized.append(
            {
                "empresa": item.get("nome_empresa") or item.get("empresa") or "Empresa sem nome",
                "telefone": item.get("telefone"),
                "email": item.get("email"),
                "site": item.get("site"),
                "cidade": item.get("cidade") or request.cidade,
                "pais": item.get("pais") or request.pais,
                "nicho": item.get("nicho") or request.nicho,
                "origem": "google_maps",
                "observacoes": item.get("observacoes") or "",
            }
        )

    real_count = len([lead for lead in normalized if (lead.get("empresa") or "").strip()])
    if real_count == 0:
        raise RuntimeError("Scraping concluiu sem leads validos")

    if progress:
        progress(95, "Leads reais coletados com sucesso")

    return normalized


def collect_leads(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    nicho = (request.nicho or "").strip()
    pais = (request.pais or "").strip()
    quantidade = max(1, min(int(request.quantidade or 1), 1000))

    if not nicho:
        raise RuntimeError("Nicho obrigatorio para scraping")
    if not pais:
        raise RuntimeError("Pais obrigatorio para scraping")

    sanitized = ScrapeRequest(
        nicho=nicho,
        cidade=(request.cidade or "").strip() or None,
        pais=pais,
        quantidade=quantidade,
    )

    if settings.scraper_mode == "google_maps":
        try:
            return asyncio.run(_run_google_maps_async(sanitized, progress))
        except Exception as exc:
            raise RuntimeError(f"Falha no scraping Google Maps: {exc}") from exc

    return _generate_mock_leads(sanitized, progress)


def _generate_mock_leads(request: ScrapeRequest, progress: ProgressCallback | None = None) -> list[dict]:
    import random
    import time

    if progress:
        progress(10, "Inicializando busca")

    nicho = request.nicho or "negocios locais"
    cidade = request.cidade
    pais = request.pais or "Brasil"
    quantidade = request.quantidade

    first_names = [
        "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa", "Rodrigues",
        "Almeida", "Nascimento", "Lima", "Araujo", "Fernandes", "Carvalho",
        "Gomes", "Martins", "Ribeiro", "Barros", "Mendes", "Moraes", "Correia",
    ]

    prefixes = [
        "Grupo", "Instituto", "Centro", "Clinica", "Escritorio", "Agencia",
        "Consultoria", "Rede", "Studio", "Nucleo", "Hub", "Lab", "Casa",
        "Associacao", "Cooperativa", "Empresa",
    ]

    cities_br = [
        "Sao Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Salvador",
        "Fortaleza", "Brasilia", "Recife", "Porto Alegre", "Goiania",
        "Manaus", "Vitoria", "Florianopolis", "Campinas", "Natal",
    ]

    domains = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br", "empresa.com.br"]

    leads: list[dict] = []
    used_names: set[str] = set()

    if progress:
        progress(25, f"Buscando {nicho} em {cidade or pais}")

    for i in range(quantidade):
        prefix = random.choice(prefixes)
        surname = random.choice(first_names)
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

        ddd = random.choice(["11", "21", "31", "41", "51", "61", "71", "81", "85", "92"])
        phone = f"({ddd}) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}" if has_phone else None
        email = f"contato@{slug}.com.br" if has_email else None
        site = f"https://www.{slug}.com.br" if has_site else None
        lead_cidade = cidade or random.choice(cities_br)

        leads.append({
            "empresa": empresa,
            "telefone": phone,
            "email": email,
            "site": site,
            "cidade": lead_cidade,
            "pais": pais,
            "nicho": nicho,
            "origem": "mock_scraper",
            "observacoes": "",
        })

        if progress and (i + 1) % max(1, quantidade // 4) == 0:
            pct = 25 + int((i / quantidade) * 65)
            progress(min(pct, 90), f"Coletados {i + 1}/{quantidade} leads")

    time.sleep(0.5)

    if progress:
        progress(95, f"{len(leads)} leads coletados com sucesso")

    return leads


def estimate_market_company_count(nicho: str, cidade: str, pais: str, sample_size: int = 120) -> int:
    sampled = collect_leads(
        ScrapeRequest(
            nicho=(nicho or "").strip() or "negocios locais",
            cidade=(cidade or "").strip() or None,
            pais=(pais or "").strip() or "Brasil",
            quantidade=max(10, min(sample_size, 200)),
        )
    )
    return len(sampled)
