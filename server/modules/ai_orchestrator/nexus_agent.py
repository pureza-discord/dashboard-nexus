from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from openai import OpenAI
from pydantic import BaseModel, Field

from server.core.settings import get_settings

settings = get_settings()

NEXUS_SYSTEM_PROMPT = """
Voce e o agente Jarvis do LeadManager.
Regras obrigatorias:
1. Sempre extraia parametros da solicitacao do usuario.
2. Antes de executar qualquer busca de leads, devolva um resumo e pergunte exatamente "Confirmar?".
3. Ferramentas so podem ser executadas apos resposta explicita de confirmacao do usuario, como: "confirmar", "sim", "pode buscar", "pode prosseguir".
4. Nunca invente ou simule leads. Somente responda com dados retornados por ferramentas reais.
5. Se faltar nicho para busca de leads, solicite o dado faltante. Quantidade padrao e 5.
6. Responda em portugues do Brasil.

Exemplos de intent "search_leads":
- "busque 5 empresas de contabilidade pelo brasil" → niche="contabilidade", quantity=5, country="Brasil"
- "quero leads de restaurantes em sao paulo" → niche="restaurantes", city="Sao Paulo", quantity=5
- "encontre 10 clinicas dentarias no rio de janeiro" → niche="clinicas dentarias", city="Rio de Janeiro", quantity=10
- "me passa empresas de marketing digital" → niche="marketing digital", quantity=5
- "procure 20 lojas de roupa em curitiba" → niche="lojas de roupa", city="Curitiba", quantity=20
- "leads de advogados" → niche="advogados", quantity=5

Se o usuario pede por empresas, leads, negocios, ou qualquer tipo de busca comercial, a intent e "search_leads".
O campo "niche" deve conter o tipo de negocio/servico, nao termos genericos como "empresas" ou "negocios locais".
Se o usuario diz "empresas de X", o niche e "X".
""".strip()


class AgentExtraction(BaseModel):
    intent: Literal["search_leads", "market", "conversation"] = "conversation"
    niche: str | None = None
    country: str | None = "Brasil"
    city: str | None = None
    quantity: int | None = Field(default=5, ge=1, le=100)
    response: str = ""
    missing_fields: list[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    user_message: str
    extraction: dict


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def _fallback_extract(message: str) -> AgentExtraction:
    text = (message or "").strip()
    lowered = text.lower()

    lead_keywords = [
        "buscar", "busque", "encontrar", "encontre", "procurar", "procure",
        "lead", "leads", "empresa", "empresas", "quero", "preciso",
        "me passa", "me traga", "pesquisar", "pesquise",
    ]

    if any(word in lowered for word in lead_keywords):
        numbers = re.findall(r"\d+", lowered)
        quantity = int(numbers[0]) if numbers else 5

        niche = None

        # Pattern 1: "[action] [N] [empresas de] [niche] [em location]"
        match_niche = re.search(
            r"(?:buscar|busque|encontrar|encontre|procurar|procure|pesquisar|pesquise|quero|preciso"
            r"|me\s+(?:passa|traga|arranja))\s+(?:\d+\s+)?(?:empresas?\s+de\s+|leads?\s+de\s+)?(.+?)(?:\s+(?:em|no|na|pelo|pela|por|pelo)\s+|$)",
            lowered,
        )
        if match_niche:
            niche = match_niche.group(1).strip()

        # Pattern 2: "leads de [niche]" or "empresas de [niche]"
        if not niche:
            match_niche2 = re.search(r"(?:leads?|empresas?)\s+de\s+(.+?)(?:\s+(?:em|no|na|pelo|pela)\s+|$)", lowered)
            if match_niche2:
                niche = match_niche2.group(1).strip()

        # Clean niche: remove trailing quantity/location fragments
        if niche:
            niche = re.sub(r"\s*\d+\s*$", "", niche).strip()
            # Remove generic wrappers
            niche = re.sub(r"^(?:empresas?\s+de\s+|leads?\s+de\s+)", "", niche).strip()
            if niche.lower() in {"empresas", "empresa", "leads", "lead", "negocios", "negocios locais", ""}:
                niche = None

        # Extract city: "em [city]" but not "em brasil" or at the very end
        city = None
        match_city = re.search(r"(?:em|na|no|pelo|pela)\s+([a-zA-Z\u00C0-\u017F][a-zA-Z\u00C0-\u017F\s]*)", text, re.IGNORECASE)
        if match_city:
            candidate = match_city.group(1).strip()
            # Filter out country-level terms
            if candidate.lower() not in {"brasil", "brazil", "todo brasil", "todo o brasil"}:
                city = candidate

        missing = []
        if not niche:
            missing.append("niche")

        return AgentExtraction(
            intent="search_leads",
            niche=niche,
            country="Brasil",
            city=city,
            quantity=max(1, min(quantity, 100)),
            response="",
            missing_fields=missing,
        )

    if any(word in lowered for word in ["mercado", "analise", "análise"]):
        return AgentExtraction(
            intent="market",
            niche="negocios locais",
            country="Brasil",
            city=None,
            quantity=1,
            response="",
            missing_fields=[],
        )

    return AgentExtraction(
        intent="conversation",
        response="Sou o Jarvis. Posso buscar leads reais por nicho e regiao. Diga algo como: busque 5 empresas de contabilidade pelo Brasil.",
    )


def _extract_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    client = _openai_client()

    if client is None:
        return {"extraction": _fallback_extract(message).model_dump()}

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["search_leads", "market", "conversation"]},
            "niche": {"type": ["string", "null"]},
            "country": {"type": ["string", "null"]},
            "city": {"type": ["string", "null"]},
            "quantity": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
            "response": {"type": "string"},
            "missing_fields": {
                "type": "array",
                "items": {"type": "string", "enum": ["niche", "country", "quantity"]},
            },
        },
        "required": ["intent", "niche", "country", "city", "quantity", "response", "missing_fields"],
        "additionalProperties": False,
    }

    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "jarvis_extraction",
                    "schema": schema,
                    "strict": True,
                },
            },
            messages=[
                {"role": "system", "content": NEXUS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Extraia intencao e parametros da mensagem abaixo. "
                        "Nao execute ferramentas, apenas retorne JSON valido no schema.\n\n"
                        f"Mensagem: {message}"
                    ),
                },
            ],
        )
        content = (completion.choices[0].message.content if completion.choices else "") or "{}"
        parsed = AgentExtraction.model_validate(json.loads(content))
        return {"extraction": parsed.model_dump()}
    except Exception:
        return {"extraction": _fallback_extract(message).model_dump()}


def _end_node(state: AgentState) -> AgentState:
    return state


@lru_cache(maxsize=1)
def _graph():
    graph = StateGraph(AgentState)
    graph.add_node("extract", _extract_node)
    graph.add_node("finalize", _end_node)
    graph.set_entry_point("extract")
    graph.add_edge("extract", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def extract_with_langgraph(user_message: str) -> AgentExtraction:
    result = _graph().invoke({"user_message": user_message})
    extraction = result.get("extraction") or {}
    return AgentExtraction.model_validate(extraction)


def is_confirmation_text(message: str) -> bool:
    text = (message or "").strip().lower()
    confirm_tokens = [
        "confirmar", "confirma", "confirmado", "confirmo",
        "sim", "ok", "yes", "pode buscar", "pode prosseguir",
        "pode executar", "pode fazer", "pode ir", "vai la",
        "manda ver", "faz isso", "execute", "executa", "bora",
        "positivo", "afirmativo", "claro", "com certeza",
    ]
    return any(token in text for token in confirm_tokens)


def is_cancellation_text(message: str) -> bool:
    text = (message or "").strip().lower()
    cancel_tokens = [
        "cancelar", "cancela", "cancelado", "cancelo",
        "nao", "não", "parar", "para", "desistir", "desisto",
        "deixa", "esquece", "nao quero", "não quero",
    ]
    return any(token in text for token in cancel_tokens)
