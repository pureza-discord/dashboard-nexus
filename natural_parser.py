import re
import unicodedata
from typing import Dict, Optional

# Palavras-chave para detectar pais
COUNTRY_KEYWORDS = {
    "brasil": "Brasil",
    "brazil": "Brasil",
    "portugal": "Portugal",
    "estados unidos": "Estados Unidos",
    "eua": "Estados Unidos",
    "usa": "Estados Unidos",
    "united states": "Estados Unidos",
    "united states of america": "Estados Unidos",
    "canada": "Canadá",
    "canadian": "Canadá",
    "australia": "Austrália",
    "australian": "Austrália",
    "todos": "Todos",
}
COUNTRY_TOKENS = {part for key in COUNTRY_KEYWORDS for part in key.split(" ")}

# Siglas de estados brasileiros
BR_STATES = {
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma",
    "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
    "rs", "ro", "rr", "sc", "sp", "se", "to",
}

# Lista de cidades conhecidas (heuristica)
KNOWN_CITIES = {
    "recife", "vitoria", "lisboa", "porto", "sydney", "melbourne",
    "brisbane", "perth", "adelaide", "fortaleza", "curitiba",
    "brasilia", "salvador", "belo horizonte", "porto alegre",
    "manaus", "sao paulo", "rio de janeiro", "goiania",
    "new york", "miami", "orlando", "los angeles", "san francisco",
    "toronto", "vancouver", "montreal",
}

# Padroes que ativam o modo procura-servico
PROCURA_SERVICO_PATTERNS = [
    r"\bprocura-servico\b",
    r"\bprocura servico\b",
    r"\bprecisa de site\b",
    r"\bcontratamos dev\b",
    r"\bquero marketing\b",
    r"\bprecisamos de\b",
    r"\bprecisamos de agencia\b",
]

VERBOS_IGNORAR = {
    "buscar", "busca", "procurar", "procuro", "quero", "preciso",
    "procurando", "procura", "empresas", "empresa", "que", "precisa",
    "precisam", "precisamos", "de", "site", "marketing", "contratamos",
}

MOJIBAKE_REPLACEMENTS = {
    "\u00c3\u00a7": "ç",
    "\u00c3\u00a3": "ã",
    "\u00c3\u00a1": "á",
    "\u00c3\u00a9": "é",
    "\u00c3\u00aa": "ê",
    "\u00c3\u00ad": "í",
    "\u00c3\u00b3": "ó",
    "\u00c3\u00b5": "õ",
    "\u00c3\u00ba": "ú",
}


def _strip_accents(texto: str) -> str:
    normalized = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _fix_mojibake(texto: str) -> str:
    fixed = texto
    for broken, expected in MOJIBAKE_REPLACEMENTS.items():
        fixed = fixed.replace(broken, expected)
    return fixed


def _normalize_text(texto: str) -> str:
    texto = _fix_mojibake(texto)
    texto = _strip_accents(texto)
    return re.sub(r"\s+", " ", texto.strip().lower())


def _detect_country(texto_normalizado: str, tokens: list[str]) -> Optional[str]:
    multi_word = sorted(
        (k for k in COUNTRY_KEYWORDS if " " in k),
        key=len,
        reverse=True,
    )
    for key in multi_word:
        if key in texto_normalizado:
            return COUNTRY_KEYWORDS[key]

    for token in tokens:
        if token in COUNTRY_KEYWORDS:
            return COUNTRY_KEYWORDS[token]
    return None


def _detect_count(tokens: list[str]) -> Optional[int]:
    for token in tokens:
        if token.isdigit():
            return int(token)
    return None


def _is_procura_servico(texto_normalizado: str) -> bool:
    return any(re.search(p, texto_normalizado) for p in PROCURA_SERVICO_PATTERNS)


def parse_natural_query(texto: str) -> Dict[str, Optional[str]]:
    """
    Interpreta frases livres em PT-BR e retorna um dicionario padronizado.
    Exemplo: "buscar 50 clinicas estetica brasil vitoria es"
    """
    texto_normalizado = _normalize_text(texto)
    tokens = texto_normalizado.split(" ")

    # Deteccao basica de pais e quantidade
    pais = _detect_country(texto_normalizado, tokens) or "Brasil"
    quantidade = _detect_count(tokens) or 50
    quantidade = max(1, min(quantidade, 500))

    # Ativa o modo procura-servico se o texto indicar
    procura_servico = _is_procura_servico(texto_normalizado)

    # Extrai raio em km (ex: "raio 10km" ou "raio 10 km")
    raio_km = None
    match_raio = re.search(r"raio\s+(\d{1,3})\s*km", texto_normalizado)
    if match_raio:
        try:
            raio_km = int(match_raio.group(1))
        except ValueError:
            raio_km = None

    # Remove palavras pouco informativas e numeros
    tokens_filtrados = [
        t
        for t in tokens
        if t not in COUNTRY_KEYWORDS
        and t not in COUNTRY_TOKENS
        and t not in VERBOS_IGNORAR
        and not t.isdigit()
    ]

    tokens_filtrados = [
        t for t in tokens_filtrados if t not in {"procura-servico", "servico"}
    ]

    cidade = None

    # Heuristica cidade-estado (ex: vitoria es)
    if len(tokens_filtrados) >= 2:
        ultimo = tokens_filtrados[-1]
        penultimo = tokens_filtrados[-2]
        if ultimo in BR_STATES:
            cidade = f"{penultimo}-{ultimo.upper()}"
            tokens_filtrados = tokens_filtrados[:-2]

    # Detecta formatos com hifen
    if not cidade and tokens_filtrados:
        ultimo = tokens_filtrados[-1]
        if "-" in ultimo:
            cidade = ultimo
            tokens_filtrados = tokens_filtrados[:-1]

    # Detecta cidade conhecida
    if not cidade and tokens_filtrados:
        ultimo = tokens_filtrados[-1]
        if ultimo in KNOWN_CITIES:
            cidade = ultimo.capitalize()
            tokens_filtrados = tokens_filtrados[:-1]

    # O restante vira o nicho
    nicho = " ".join(tokens_filtrados).strip() or "Negocios locais"

    return {
        "pais": pais,
        "nicho": nicho,
        "cidade": cidade,
        "limite": quantidade,
        "procura_servico": procura_servico,
        "raio_km": raio_km,
    }
