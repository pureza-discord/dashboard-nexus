"""
Real AI Agent with OpenAI Tool Calling.

Flow: message -> OpenAI (with tools) -> detect tool_call -> execute tool -> return final answer.
The AI generates a human-readable summary after tool execution.
"""

import json
import re
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from server.core.settings import get_settings
from server.db.models import Lead, User

settings = get_settings()

# ── OpenAI Tools Definition ──────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_companies",
            "description": (
                "Buscar empresas/leads reais por nicho e localizacao. "
                "Use quando o usuario pedir para buscar, encontrar, coletar empresas ou leads."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nicho": {"type": "string", "description": "Segmento/nicho das empresas (ex: contabilidade, clinica estetica)"},
                    "cidade": {"type": ["string", "null"], "description": "Cidade especifica ou null para busca nacional"},
                    "pais": {"type": "string", "description": "Pais da busca (default: Brasil)"},
                    "quantidade": {"type": "integer", "description": "Quantidade exata de empresas solicitada"},
                    "aleatorio": {"type": "boolean", "description": "true se busca nacional/pelo Brasil sem cidade especifica"},
                },
                "required": ["nicho", "pais", "quantidade"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_workana",
            "description": "Buscar projetos abertos na plataforma Workana (freelance).",
            "parameters": {
                "type": "object",
                "properties": {
                    "servico": {"type": "string", "description": "Tipo de servico a buscar"},
                    "pais": {"type": "string", "description": "Pais"},
                },
                "required": ["servico", "pais"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_services",
            "description": "Buscar pessoas/empresas que estao PROCURANDO contratar servicos (deep search).",
            "parameters": {
                "type": "object",
                "properties": {
                    "servico": {"type": "string", "description": "Tipo de servico procurado"},
                    "pais": {"type": "string", "description": "Pais"},
                    "cidade": {"type": ["string", "null"], "description": "Cidade ou null"},
                },
                "required": ["servico", "pais"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_market",
            "description": "Analisar mercado, oportunidades, saturacao e tendencias de um nicho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nicho": {"type": "string"},
                    "cidade": {"type": ["string", "null"]},
                    "pais": {"type": "string"},
                },
                "required": ["nicho", "pais"],
            },
        },
    },
]

TOOL_TO_INTENT = {
    "search_companies": "scrape",
    "search_workana": "workana",
    "search_services": "services",
    "analyze_market": "market",
}

SYSTEM_PROMPT = (
    "Voce e Nexus AI, agente de inteligencia comercial da Nexus Leads. "
    "Seu papel: interpretar pedidos do usuario e executar ferramentas para buscar leads reais, "
    "analisar mercado e orientar estrategia comercial. "
    "Regras: "
    "1. Nunca invente dados ou leads. Sempre use as tools disponiveis. "
    "2. Se o usuario pedir para buscar empresas/leads, use search_companies. "
    "3. Se mencionar Workana, use search_workana. "
    "4. Se pedir quem procura servicos, use search_services. "
    "5. Se pedir analise de mercado, use analyze_market. "
    "6. Se cidade nao for especificada ou disser 'pelo Brasil'/'nacional', passe cidade=null e aleatorio=true. "
    "7. Respeite a quantidade EXATA pedida pelo usuario. Se pedir 5, passe quantidade=5. "
    "8. Para conversa geral, responda normalmente sem chamar tools. "
    "9. Seja conciso e profissional (2-4 frases). "
    "10. Responda em portugues brasileiro."
)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured.",
        )
    return OpenAI(api_key=settings.openai_api_key)


def _get_existing_leads_fingerprints(db: Session, user: User, limit: int = 500) -> set[str]:
    """Get fingerprints of user's existing leads to avoid duplicates."""
    rows = (
        db.query(Lead.fingerprint)
        .filter(Lead.user_id == user.id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .all()
    )
    return {r[0] for r in rows}


def _build_conversation(history: list[dict], user_message: str) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history[-10:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:2500]})
    messages.append({"role": "user", "content": user_message})
    return messages


def classify_message(history: list[dict], user_message: str) -> dict:
    """
    Send message to OpenAI with tools. Returns:
    - If tool_call: {"intent": str, "tool_name": str, "tool_args": dict, "assistant_reply": ""}
    - If no tool: {"intent": "assistant", "assistant_reply": str}
    """
    messages = _build_conversation(history, user_message)

    try:
        completion = _client().chat.completions.create(
            model=settings.openai_model,
            temperature=0.15,
            tools=TOOLS,
            tool_choice="auto",
            messages=messages,
        )
    except HTTPException:
        raise
    except Exception:
        return _fallback_classify(user_message)

    choice = completion.choices[0] if completion.choices else None
    if not choice:
        return _fallback_classify(user_message)

    msg = choice.message

    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        fn_name = tool_call.function.name
        try:
            fn_args = json.loads(tool_call.function.arguments)
        except Exception:
            fn_args = {}

        intent = TOOL_TO_INTENT.get(fn_name, "assistant")
        return {
            "intent": intent,
            "tool_name": fn_name,
            "tool_args": fn_args,
            "tool_call_id": tool_call.id,
            "assistant_reply": "",
        }

    content = (msg.content or "").strip()
    return {
        "intent": "assistant",
        "tool_name": None,
        "tool_args": {},
        "assistant_reply": content or "Como posso ajudar?",
    }


def generate_tool_result_summary(
    history: list[dict],
    user_message: str,
    tool_name: str,
    tool_call_id: str,
    tool_result: dict,
) -> str:
    """
    After tool execution, send the result back to OpenAI to get a natural summary.
    This is the second call in the tool-calling loop.
    """
    messages = _build_conversation(history, user_message)

    # Add the assistant message with tool call
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(tool_result.get("tool_args", {})),
            },
        }],
    })

    # Add tool result
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(tool_result, ensure_ascii=False, default=str)[:3000],
    })

    try:
        completion = _client().chat.completions.create(
            model=settings.openai_model,
            temperature=0.3,
            max_tokens=500,
            messages=messages,
        )
        content = (completion.choices[0].message.content if completion.choices else "").strip()
        return content or "Tarefa concluida."
    except Exception:
        # Fallback summary
        inserted = tool_result.get("inserted", 0)
        total = tool_result.get("total_received", 0)
        if inserted > 0:
            return f"Encontrei {inserted} leads novos (total processado: {total})."
        return "Tarefa concluida."


def _fallback_classify(message: str) -> dict:
    """Keyword-based fallback if OpenAI is unavailable."""
    text = message.lower()

    scrape_tokens = [
        "buscar", "busque", "busca", "encontrar", "encontre", "coletar",
        "procurar", "procure", "empresa", "empresas", "leads", "listar",
    ]
    if any(t in text for t in scrape_tokens):
        qty = 50
        nums = re.findall(r"\d+", message)
        if nums:
            qty = max(1, min(int(nums[0]), 1000))

        return {
            "intent": "scrape",
            "tool_name": "search_companies",
            "tool_args": {
                "nicho": "negocios locais",
                "pais": "Brasil",
                "quantidade": qty,
                "aleatorio": True,
            },
            "tool_call_id": "fallback",
            "assistant_reply": "",
        }

    if "workana" in text:
        return {
            "intent": "workana",
            "tool_name": "search_workana",
            "tool_args": {"servico": "desenvolvimento web", "pais": "Brasil"},
            "tool_call_id": "fallback",
            "assistant_reply": "",
        }

    if any(t in text for t in ["mercado", "analise", "análise", "saturacao"]):
        return {
            "intent": "market",
            "tool_name": "analyze_market",
            "tool_args": {"nicho": "negocios locais", "pais": "Brasil"},
            "tool_call_id": "fallback",
            "assistant_reply": "",
        }

    return {
        "intent": "assistant",
        "tool_name": None,
        "tool_args": {},
        "assistant_reply": "Posso buscar leads, analisar mercado ou buscar projetos no Workana. Como posso ajudar?",
    }
