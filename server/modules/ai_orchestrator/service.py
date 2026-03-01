import json
import uuid
from functools import lru_cache
from typing import Literal

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from natural_parser import parse_natural_query
from server.core.settings import get_settings
from server.db.models import AIMessage, AITask, Lead, LeadStatus, MessageRole, TaskStatus, TaskType, User
from server.modules.analytics.service import quick_metrics
from server.modules.billing.service import assert_external_query_quota, assert_lead_quota
from server.workers.tasks import run_market_task, run_scrape_task

settings = get_settings()

Intent = Literal["scrape", "market", "assistant", "clarify"]


def _canonical_id(raw: str) -> str:
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(raw).strip()


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured on backend.",
        )
    return OpenAI(api_key=settings.openai_api_key)


def _message_to_dict(message: AIMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role.value,
        "content": message.content,
        "task_id": str(message.task_id) if message.task_id else None,
        "metadata": message.message_metadata or {},
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _task_to_dict(task: AITask) -> dict:
    return {
        "id": str(task.id),
        "task_type": task.task_type.value,
        "status": task.status.value,
        "progress": task.progress,
        "requested_quantity": task.requested_quantity,
        "completed_quantity": task.completed_quantity,
        "prompt": task.prompt,
        "parsed_payload": task.parsed_payload or {},
        "result_payload": task.result_payload or {},
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _save_message(
    db: Session,
    *,
    user: User,
    role: MessageRole,
    content: str,
    task_id: str | None = None,
    metadata: dict | None = None,
) -> AIMessage:
    row = AIMessage(
        user_id=user.id,
        task_id=task_id,
        role=role,
        content=content,
        message_metadata=metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _create_task(
    db: Session,
    user: User,
    *,
    task_type: TaskType,
    prompt: str,
    parsed_payload: dict,
    requested_quantity: int,
) -> AITask:
    task = AITask(
        user_id=user.id,
        task_type=task_type,
        status=TaskStatus.queued,
        progress=0,
        prompt=prompt,
        parsed_payload=parsed_payload,
        requested_quantity=requested_quantity,
        completed_quantity=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _recent_messages_for_llm(db: Session, user: User, limit: int = 12) -> list[dict]:
    rows = (
        db.query(AIMessage)
        .filter(AIMessage.user_id == user.id)
        .order_by(AIMessage.created_at.desc())
        .limit(max(1, min(limit, 30)))
        .all()
    )
    items: list[dict] = []
    for row in reversed(rows):
        if row.role not in {MessageRole.user, MessageRole.assistant}:
            continue
        role = "assistant" if row.role == MessageRole.assistant else "user"
        content = str(row.content or "").strip()
        if not content:
            continue
        items.append({"role": role, "content": content[:2500]})
    return items


def _extract_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        fragment = text[start : end + 1]
        try:
            parsed = json.loads(fragment)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}

    return {}


def _normalize_country(raw_country: str | None) -> str:
    country = (raw_country or "").strip().lower()
    if country in {"", "br", "brasil", "brazil"}:
        return "Brasil"
    if country in {"portugal", "pt"}:
        return "Portugal"
    if country in {"australia", "au", "australia."}:
        return "Australia"
    if country in {"eua", "usa", "estados unidos", "united states"}:
        return "Estados Unidos"
    return (raw_country or "Brasil").strip()


def _normalize_city(raw_city: str | None) -> str | None:
    value = (raw_city or "").strip()
    if not value:
        return None
    normalized = value.lower()
    if normalized in {
        "brasil",
        "brazil",
        "nacional",
        "todo brasil",
        "todo o brasil",
        "em todo brasil",
        "em todo o brasil",
        "nationwide",
        "countrywide",
    }:
        return None
    return value


def _coerce_quantity(raw_quantity: int | float | str | None) -> int:
    try:
        qty = int(raw_quantity or 50)
    except Exception:
        qty = 50
    return max(1, min(qty, 1000))


def _fallback_parse(message: str) -> dict:
    parsed = parse_natural_query(message)
    text = message.lower()

    intent: Intent = "assistant"
    scrape_tokens = [
        "buscar", "busque", "busca", "busco",
        "leads", "scraping", "scrape",
        "encontrar", "encontre", "encontro",
        "coletar", "colete", "coleta",
        "procurar", "procure", "procuro",
        "pesquisar", "pesquise", "pesquiso",
        "empresa", "empresas",
        "pegar", "pegue",
        "listar", "liste",
        "achar", "ache",
    ]
    if any(token in text for token in scrape_tokens):
        intent = "scrape"
    if any(token in text for token in ["mercado", "oportunidade", "saturacao", "saturação", "tendencia", "analise", "análise"]):
        intent = "market"

    city = _normalize_city(parsed.get("cidade"))
    country = _normalize_country(parsed.get("pais"))

    return {
        "intent": intent,
        "nicho": str(parsed.get("nicho") or "negocios locais").strip(),
        "cidade": city,
        "pais": country,
        "quantidade": _coerce_quantity(parsed.get("limite")),
        "requires_confirmation": intent in {"scrape", "market"},
        "assistant_reply": "",
    }


def _classify_with_openai(db: Session, user: User, message: str) -> dict:
    history = _recent_messages_for_llm(db, user)

    system_prompt = (
        "Voce e Nexus Scraper, inteligencia operacional da Nexus Leads. "
        "Seu papel: interpretar pedidos, buscar leads reais, analisar mercado e orientar estrategia comercial. "
        "Nunca invente dados. Nunca prometa resultado que nao exista. "
        "Para scraping e analise de mercado, sempre exija confirmacao antes da execucao. "
        "Se o pedido estiver ambiguo, retorne intent=clarify com uma pergunta objetiva. "
        "Se cidade nao for informada, defina cidade=null para escopo nacional. "
        "Responda APENAS JSON valido com as chaves: "
        "intent, nicho, cidade, pais, quantidade, requires_confirmation, assistant_reply. "
        "intent deve ser um de: scrape, market, assistant, clarify."
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        completion = _openai_client().chat.completions.create(
            model=settings.openai_model,
            temperature=0.15,
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = completion.choices[0].message.content if completion.choices else "{}"
        parsed = _extract_json_object(content or "{}")
        if not parsed:
            return _fallback_parse(message)
        return parsed
    except HTTPException:
        raise
    except Exception:
        # Fallback parser is used only if provider is temporarily unavailable.
        return _fallback_parse(message)


def _coerce_intent(value: str | None) -> Intent:
    normalized = (value or "assistant").strip().lower()
    if normalized in {"scrape", "market", "assistant", "clarify"}:
        return normalized  # type: ignore[return-value]
    return "assistant"


def _build_prioritization_hint(db: Session, user: User) -> str:
    top_leads = (
        db.query(Lead)
        .filter(Lead.user_id == user.id, Lead.status.in_([LeadStatus.novos, LeadStatus.contatados, LeadStatus.proposta]))
        .order_by(Lead.score.desc(), Lead.ticket_estimado.desc())
        .limit(3)
        .all()
    )
    if not top_leads:
        return "Sem leads priorizados no momento. Inicie uma busca para gerar novas oportunidades."

    parts = []
    for lead in top_leads:
        parts.append(
            f"{lead.empresa} (score {lead.score}, chance {round(float(lead.chance_fechamento or 0), 1)}%)"
        )
    return "Priorize follow-up em: " + "; ".join(parts) + "."


def _generate_conversational_reply(
    db: Session,
    user: User,
    user_message: str,
    metrics: dict,
    prioritization: str,
) -> str:
    """Gera resposta natural e contextualizada via OpenAI para conversa geral."""
    history = _recent_messages_for_llm(db, user, limit=10)
    context = (
        f"Contexto atual do usuário: {metrics['total']} leads no funil, "
        f"taxa de conversão {metrics['conversion_rate']}%. {prioritization}"
    )
    system = (
        "Você é o assistente do Nexus Leads Manager, uma IA de inteligência comercial. "
        "Responda de forma natural, objetiva e profissional. Use o contexto do funil de leads quando relevante. "
        "Você pode falar sobre empresas, leads, pipeline, scraping, análise de mercado e próximos passos. "
        "Seja conciso (1-3 frases). Não invente dados que não estejam no contexto. "
        "Contexto: " + context
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        completion = _openai_client().chat.completions.create(
            model=settings.openai_model,
            temperature=0.4,
            max_tokens=400,
            messages=messages,
        )
        content = (completion.choices[0].message.content if completion.choices else "" or "").strip()
        return content if content else (
            "Posso iniciar uma busca de leads ou análise de mercado. "
            f"Seu funil tem {metrics['total']} leads. {prioritization}"
        )
    except HTTPException:
        raise
    except Exception:
        return (
            "Posso iniciar scraping de leads reais ou análise de mercado. "
            f"Funil atual: {metrics['total']} leads e conversão de {metrics['conversion_rate']}%. "
            f"{prioritization}"
        )


def handle_chat(db: Session, user: User, message: str, confirm_execution: bool) -> dict:
    user_message = _save_message(db, user=user, role=MessageRole.user, content=message)

    ai_decision = _classify_with_openai(db, user, message)
    intent = _coerce_intent(str(ai_decision.get("intent") or "assistant"))

    nicho = str(ai_decision.get("nicho") or "negocios locais").strip() or "negocios locais"
    cidade = _normalize_city(ai_decision.get("cidade"))
    pais = _normalize_country(ai_decision.get("pais"))
    quantidade = _coerce_quantity(ai_decision.get("quantidade"))
    requires_confirmation = bool(ai_decision.get("requires_confirmation", intent in {"scrape", "market"}))
    assistant_reply = str(ai_decision.get("assistant_reply") or "").strip()

    if intent == "clarify":
        clarification = assistant_reply or (
            "Pode detalhar melhor o pedido? Informe nicho, cidade (ou nacional) e quantidade de leads."
        )
        assistant_message = _save_message(
            db,
            user=user,
            role=MessageRole.assistant,
            content=clarification,
            metadata={"intent": "clarify", "requires_confirmation": False},
        )
        return {
            "intent": "clarify",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    if intent == "scrape":
        parsed = {
            "nicho": nicho,
            "cidade": cidade,
            "pais": pais,
            "quantidade": quantidade,
            "scope": "nacional" if cidade is None else "cidade",
        }
        assert_lead_quota(user, quantidade)

        if not confirm_execution:
            city_label = "Nacional" if cidade is None else cidade
            assistant_text = (
                "Confirma iniciar scraping real agora? "
                f"Nicho: {nicho}, Cidade: {city_label}, Pais: {pais}, Quantidade: {quantidade} leads."
            )
            assistant_message = _save_message(
                db,
                user=user,
                role=MessageRole.assistant,
                content=assistant_text,
                metadata={
                    "intent": "scrape",
                    "requires_confirmation": True,
                    "requested_requires_confirmation": requires_confirmation,
                    "parsed": parsed,
                },
            )
            return {
                "intent": "scrape",
                "requires_confirmation": True,
                "parsed_request": parsed,
                "assistant_message": _message_to_dict(assistant_message),
                "user_message": _message_to_dict(user_message),
            }

        task = _create_task(
            db,
            user,
            task_type=TaskType.scraping,
            prompt=message,
            parsed_payload=parsed,
            requested_quantity=quantidade,
        )
        async_job = run_scrape_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)
        db.commit()
        db.refresh(task)

        assistant_message = _save_message(
            db,
            user=user,
            role=MessageRole.assistant,
            content=(
                assistant_reply
                or "Busca iniciada. Vou atualizar o progresso e inserir apenas leads reais no seu painel."
            ),
            task_id=task.id,
            metadata={
                "intent": "scrape",
                "requires_confirmation": False,
                "task_id": str(task.id),
            },
        )

        return {
            "intent": "scrape",
            "requires_confirmation": False,
            "parsed_request": parsed,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    if intent == "market":
        parsed = {
            "nicho": nicho,
            "cidade": cidade or "Brasil",
            "pais": pais,
        }
        assert_external_query_quota(user, 1)

        if not confirm_execution:
            city_label = "Nacional" if cidade is None else cidade
            assistant_text = (
                "Confirma gerar relatorio de inteligencia de mercado com dados externos reais? "
                f"Nicho: {nicho}, Cidade: {city_label}, Pais: {pais}."
            )
            assistant_message = _save_message(
                db,
                user=user,
                role=MessageRole.assistant,
                content=assistant_text,
                metadata={
                    "intent": "market",
                    "requires_confirmation": True,
                    "requested_requires_confirmation": requires_confirmation,
                    "parsed": parsed,
                },
            )
            return {
                "intent": "market",
                "requires_confirmation": True,
                "parsed_request": parsed,
                "assistant_message": _message_to_dict(assistant_message),
                "user_message": _message_to_dict(user_message),
            }

        task = _create_task(
            db,
            user,
            task_type=TaskType.market_intelligence,
            prompt=message,
            parsed_payload=parsed,
            requested_quantity=1,
        )
        async_job = run_market_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)
        db.commit()
        db.refresh(task)

        assistant_message = _save_message(
            db,
            user=user,
            role=MessageRole.assistant,
            content=(
                assistant_reply
                or "Relatorio iniciado. Vou retornar score de oportunidade e riscos com base em dados reais."
            ),
            task_id=task.id,
            metadata={"intent": "market", "task_id": str(task.id)},
        )

        return {
            "intent": "market",
            "requires_confirmation": False,
            "parsed_request": parsed,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    metrics = quick_metrics(db, user)
    prioritization = _build_prioritization_hint(db, user)
    conversational = _generate_conversational_reply(db, user, message, metrics, prioritization)
    assistant_message = _save_message(
        db,
        user=user,
        role=MessageRole.assistant,
        content=assistant_reply or conversational,
        metadata={"intent": "assistant", "requires_confirmation": False},
    )
    return {
        "intent": "assistant",
        "requires_confirmation": False,
        "assistant_message": _message_to_dict(assistant_message),
        "user_message": _message_to_dict(user_message),
    }


def list_messages(db: Session, user: User, limit: int = 50) -> list[dict]:
    rows = (
        db.query(AIMessage)
        .filter(AIMessage.user_id == user.id)
        .order_by(AIMessage.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_message_to_dict(item) for item in reversed(rows)]


def list_tasks(db: Session, user: User, limit: int = 20) -> list[dict]:
    rows = (
        db.query(AITask)
        .filter(AITask.user_id == user.id)
        .order_by(AITask.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [_task_to_dict(item) for item in rows]


def get_task(db: Session, user: User, task_id: str) -> dict:
    parsed_task_id = _canonical_id(task_id)
    if not parsed_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task id")

    task = db.query(AITask).filter(AITask.id == parsed_task_id, AITask.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return _task_to_dict(task)
