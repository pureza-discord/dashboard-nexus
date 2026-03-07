"""Strict geo-validation + region/state expansion."""

import logging

logger = logging.getLogger("scraper.geo")

# Known city → country mappings for strict validation.
# This is NOT exhaustive — it validates common cases and catches mismatches.
# Cities not in this map are allowed through (we trust the LLM/user).
CITY_COUNTRY_MAP: dict[str, set[str]] = {
    # Portugal
    "lisboa": {"Portugal"},
    "porto": {"Portugal"},
    "coimbra": {"Portugal"},
    "braga": {"Portugal"},
    "faro": {"Portugal"},
    "funchal": {"Portugal"},
    "aveiro": {"Portugal"},
    "evora": {"Portugal"},
    "setubal": {"Portugal"},
    "viseu": {"Portugal"},
    "leiria": {"Portugal"},
    # Brazil
    "sao paulo": {"Brasil", "Brazil"},
    "rio de janeiro": {"Brasil", "Brazil"},
    "belo horizonte": {"Brasil", "Brazil"},
    "curitiba": {"Brasil", "Brazil"},
    "salvador": {"Brasil", "Brazil"},
    "fortaleza": {"Brasil", "Brazil"},
    "brasilia": {"Brasil", "Brazil"},
    "recife": {"Brasil", "Brazil"},
    "porto alegre": {"Brasil", "Brazil"},
    "goiania": {"Brasil", "Brazil"},
    "manaus": {"Brasil", "Brazil"},
    "vitoria": {"Brasil", "Brazil"},
    "florianopolis": {"Brasil", "Brazil"},
    "campinas": {"Brasil", "Brazil"},
    "natal": {"Brasil", "Brazil"},
    "belem": {"Brasil", "Brazil"},
    # USA
    "new york": {"Estados Unidos", "United States", "USA"},
    "los angeles": {"Estados Unidos", "United States", "USA"},
    "chicago": {"Estados Unidos", "United States", "USA"},
    "houston": {"Estados Unidos", "United States", "USA"},
    "miami": {"Estados Unidos", "United States", "USA"},
    "san francisco": {"Estados Unidos", "United States", "USA"},
    "seattle": {"Estados Unidos", "United States", "USA"},
    "boston": {"Estados Unidos", "United States", "USA"},
    "dallas": {"Estados Unidos", "United States", "USA"},
    "austin": {"Estados Unidos", "United States", "USA"},
    "denver": {"Estados Unidos", "United States", "USA"},
    "atlanta": {"Estados Unidos", "United States", "USA"},
    "phoenix": {"Estados Unidos", "United States", "USA"},
    "las vegas": {"Estados Unidos", "United States", "USA"},
    "washington": {"Estados Unidos", "United States", "USA"},
    # Canada
    "toronto": {"Canada", "Canadá"},
    "vancouver": {"Canada", "Canadá"},
    "montreal": {"Canada", "Canadá"},
    "ottawa": {"Canada", "Canadá"},
    "calgary": {"Canada", "Canadá"},
    # Australia
    "sydney": {"Australia", "Austrália"},
    "melbourne": {"Australia", "Austrália"},
    "brisbane": {"Australia", "Austrália"},
    "perth": {"Australia", "Austrália"},
    "adelaide": {"Australia", "Austrália"},
    # UK
    "london": {"United Kingdom", "UK", "Reino Unido"},
    "manchester": {"United Kingdom", "UK", "Reino Unido"},
    "birmingham": {"United Kingdom", "UK", "Reino Unido"},
    "edinburgh": {"United Kingdom", "UK", "Reino Unido"},
    # Spain
    "madrid": {"Spain", "España", "Espanha"},
    "barcelona": {"Spain", "España", "Espanha"},
    "valencia": {"Spain", "España", "Espanha"},
    "seville": {"Spain", "España", "Espanha"},
    "sevilla": {"Spain", "España", "Espanha"},
    # Germany
    "berlin": {"Germany", "Deutschland", "Alemanha"},
    "munich": {"Germany", "Deutschland", "Alemanha"},
    "hamburg": {"Germany", "Deutschland", "Alemanha"},
    "frankfurt": {"Germany", "Deutschland", "Alemanha"},
    # France
    "paris": {"France", "França"},
    "lyon": {"France", "França"},
    "marseille": {"France", "França"},
    # Italy
    "rome": {"Italy", "Italia", "Itália"},
    "roma": {"Italy", "Italia", "Itália"},
    "milan": {"Italy", "Italia", "Itália"},
    "milano": {"Italy", "Italia", "Itália"},
    # Japan
    "tokyo": {"Japan", "Japão"},
    "osaka": {"Japan", "Japão"},
    # Mexico
    "mexico city": {"Mexico", "México"},
    "guadalajara": {"Mexico", "México"},
    "monterrey": {"Mexico", "México"},
    # Argentina
    "buenos aires": {"Argentina"},
    # Colombia
    "bogota": {"Colombia", "Colômbia"},
    "medellin": {"Colombia", "Colômbia"},
    # Chile
    "santiago": {"Chile"},
}


# ---------------------------------------------------------------------------
# Region → cities expansion (Brazil)
# ---------------------------------------------------------------------------

REGION_CITIES: dict[str, list[str]] = {
    "nordeste": ["Recife", "Salvador", "Fortaleza", "Natal", "São Luís", "João Pessoa", "Maceió", "Aracaju", "Teresina"],
    "sudeste": ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Vitória", "Campinas", "Santos", "Niterói"],
    "sul": ["Curitiba", "Porto Alegre", "Florianópolis", "Joinville", "Londrina", "Caxias do Sul"],
    "norte": ["Manaus", "Belém", "Porto Velho", "Macapá", "Boa Vista", "Rio Branco", "Palmas"],
    "centro-oeste": ["Brasília", "Goiânia", "Campo Grande", "Cuiabá"],
}

# Brazilian state abbreviation → main cities
STATE_CITIES: dict[str, list[str]] = {
    "sp": ["São Paulo", "Campinas", "Santos", "Ribeirão Preto", "Sorocaba", "São José dos Campos"],
    "rj": ["Rio de Janeiro", "Niterói", "São Gonçalo", "Duque de Caxias", "Petrópolis"],
    "mg": ["Belo Horizonte", "Uberlândia", "Contagem", "Juiz de Fora", "Betim"],
    "rs": ["Porto Alegre", "Caxias do Sul", "Pelotas", "Canoas", "Santa Maria"],
    "pr": ["Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel"],
    "sc": ["Florianópolis", "Joinville", "Blumenau", "Chapecó", "Criciúma"],
    "ba": ["Salvador", "Feira de Santana", "Vitória da Conquista", "Camaçari"],
    "pe": ["Recife", "Jaboatão dos Guararapes", "Olinda", "Caruaru"],
    "ce": ["Fortaleza", "Caucaia", "Juazeiro do Norte", "Sobral"],
    "go": ["Goiânia", "Aparecida de Goiânia", "Anápolis"],
    "pa": ["Belém", "Ananindeua", "Santarém", "Marabá"],
    "am": ["Manaus", "Parintins"],
    "df": ["Brasília"],
    "es": ["Vitória", "Vila Velha", "Serra", "Cariacica"],
    "rn": ["Natal", "Mossoró", "Parnamirim"],
    "ma": ["São Luís", "Imperatriz"],
    "pb": ["João Pessoa", "Campina Grande"],
    "al": ["Maceió", "Arapiraca"],
    "se": ["Aracaju"],
    "pi": ["Teresina"],
    "mt": ["Cuiabá", "Várzea Grande", "Rondonópolis"],
    "ms": ["Campo Grande", "Dourados"],
    "to": ["Palmas"],
    "ro": ["Porto Velho", "Ji-Paraná"],
    "ac": ["Rio Branco"],
    "ap": ["Macapá"],
    "rr": ["Boa Vista"],
}


def expand_geo(
    estado: str | None,
    cidade: str | None,
    pais: str,
) -> list[str | None]:
    """Expand estado/region into a list of cities.

    Returns:
        List of city names, or [None] for national scope, or [cidade] if specific.
    """
    if cidade:
        return [cidade]

    if estado:
        key = estado.lower().strip()
        # Check region names
        if key in REGION_CITIES:
            logger.info("[SCRAPER GEO] Expanding region '%s' → %d cities", estado, len(REGION_CITIES[key]))
            return REGION_CITIES[key]
        # Check state abbreviations
        if key in STATE_CITIES:
            logger.info("[SCRAPER GEO] Expanding state '%s' → %d cities", estado, len(STATE_CITIES[key]))
            return STATE_CITIES[key]
        # Treat as a single city-like string
        return [estado]

    # National scope
    return [None]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class GeoValidationError(Exception):
    """Raised when city does not belong to the specified country."""

    def __init__(self, cidade: str, pais: str, valid_countries: set[str]) -> None:
        self.cidade = cidade
        self.pais = pais
        self.valid_countries = valid_countries
        super().__init__(
            f"City '{cidade}' does not belong to country '{pais}'. "
            f"Known countries for this city: {', '.join(sorted(valid_countries))}."
        )


def validate_geo(pais: str, cidade: str | None) -> tuple[str, str | None]:
    """Validate and return (pais, cidade). Raises GeoValidationError on mismatch.

    Rules:
    - pais is REQUIRED and must be non-empty.
    - cidade is optional (None = national scope).
    - If cidade is in CITY_COUNTRY_MAP and pais doesn't match, raise error.
    - If cidade is NOT in the map, allow it through (trust the caller).
    - NO fallbacks. NO defaults. NO auto-correction.
    """
    pais = (pais or "").strip()
    if not pais:
        raise ValueError("Country (pais) is required. No default will be assumed.")

    if cidade is None:
        logger.debug("[SCRAPER GEO] Validated: pais=%s, cidade=national", pais)
        return pais, None

    cidade = cidade.strip()
    if not cidade:
        logger.debug("[SCRAPER GEO] Validated: pais=%s, cidade=national (empty)", pais)
        return pais, None

    normalized_city = cidade.lower().strip()

    if normalized_city in CITY_COUNTRY_MAP:
        valid_countries = CITY_COUNTRY_MAP[normalized_city]
        if not any(pais.lower() == vc.lower() for vc in valid_countries):
            logger.warning(
                "[SCRAPER GEO] Mismatch: cidade=%s, pais=%s, valid=%s",
                cidade, pais, valid_countries,
            )
            raise GeoValidationError(cidade, pais, valid_countries)

    logger.debug("[SCRAPER GEO] Validated: pais=%s, cidade=%s", pais, cidade)
    return pais, cidade

