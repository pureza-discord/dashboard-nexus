import json
import logging
import uuid
from functools import lru_cache

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from server.core.settings import get_settings
from server.db.models import AIMessage, AITask, Lead, LeadStatus, MessageRole, TaskStatus, TaskType, User
from server.modules.analytics.service import quick_metrics
from server.modules.billing.service import (
    assert_external_query_quota,
    assert_lead_quota,
    assert_source_allowed,
    consume_ai_message,
    get_policy,
    usage_payload,
)
from server.workers.tasks import run_market_task, run_scrape_task

settings = get_settings()
logger = logging.getLogger("ai_orchestrator")

BUSCAR_LEADS_TOOL = {
    "type": "function",
    "function": {
        "name": "buscar_leads",
        "description": (
            "Search for real business leads worldwide using multiple sources. "
            "Returns actual company data (name, phone, email, website, address)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nicho": {"type": "string", "description": "Business niche/category to search (e.g., 'dental clinics', 'accounting firms', 'restaurants')"},
                "pais": {"type": "string", "description": "Country to search in (e.g., 'Brasil', 'Portugal', 'United States', 'Canada')"},
                "cidade": {"type": ["string", "null"], "description": "City to search in, or null for national scope (e.g., 'São Paulo', 'Lisboa', 'Toronto')"},
                "estado": {"type": ["string", "null"], "description": "State or region for targeted search (e.g., 'SP', 'nordeste', 'California'). null if not specified."},
                "quantidade": {"type": "integer", "description": "Number of leads to fetch (1-1000)"},
                "fonte": {
                    "type": "string",
                    "enum": ["google_maps", "workana", "linkedin", "facebook"],
                    "description": "Data source to use. Default: google_maps. Use workana for freelance jobs.",
                },
            },
            "required": ["nicho", "pais", "quantidade"],
        },
    },
}

ANALISAR_MERCADO_TOOL = {
    "type": "function",
    "function": {
        "name": "analisar_mercado",
        "description": "Run market intelligence analysis for a niche and region.",
        "parameters": {
            "type": "object",
            "properties": {
                "nicho": {"type": "string", "description": "Business niche/category to analyze"},
                "pais": {"type": "string", "description": "Country to analyze"},
                "cidade": {"type": ["string", "null"], "description": "City to analyze, or null for national scope"},
            },
            "required": ["nicho", "pais"],
        },
    },
}

TOOLS = [BUSCAR_LEADS_TOOL, ANALISAR_MERCADO_TOOL]


def _canonical_id(raw: str) -> str:
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(raw).strip()


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
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


def _coerce_quantity(raw_quantity: int | float | str | None) -> int:
    try:
        qty = int(raw_quantity or 50)
    except Exception:
        qty = 50
    return max(1, min(qty, 1000))


def _build_prioritization_hint(db: Session, user: User) -> str:
    top_leads = (
        db.query(Lead)
        .filter(Lead.user_id == user.id, Lead.status.in_([LeadStatus.novos, LeadStatus.contatados, LeadStatus.proposta]))
        .order_by(Lead.score.desc(), Lead.ticket_estimado.desc())
        .limit(3)
        .all()
    )
    if not top_leads:
        return "No prioritized leads at the moment. Start a search to generate new opportunities."

    parts = []
    for lead in top_leads:
        parts.append(
            f"{lead.empresa} (score {lead.score}, chance {round(float(lead.chance_fechamento or 0), 1)}%)"
        )
    return "Prioritize follow-up on: " + "; ".join(parts) + "."


def _get_status_counts(db: Session, user: User) -> dict:
    counts = {}
    for st in [LeadStatus.novos, LeadStatus.contatados, LeadStatus.proposta, LeadStatus.fechados, LeadStatus.perdidos]:
        counts[st.value] = db.query(Lead).filter(Lead.user_id == user.id, Lead.status == st).count()
    return counts


def _build_system_prompt(metrics: dict, prioritization: str, user: User | None = None) -> str:
    total = metrics.get("total", 0)
    conv_rate = metrics.get("conversion_rate", 0)

    credit_context = ""
    if user:
        policy = get_policy(user.plan_type)
        if policy.monthly_credits is None:
            credit_context = f"Plan: {policy.display_name} (unlimited credits)."
        else:
            credit_context = (
                f"Plan: {policy.display_name}. "
                f"Credits: {user.credits_balance}/{policy.monthly_credits}."
            )

    return (
        "You are LeadAI Global, a world-class AI lead generation agent.\n"
        "You are NOT a chatbot. You are a strategic business intelligence partner.\n\n"
        "PERSONALITY:\n"
        "- Proactive, strategic, and results-driven\n"
        "- Speak naturally in the user's language (detect from their message)\n"
        "- Suggest smart strategies, not just execute commands\n"
        "- When delivering results, highlight actionable insights\n\n"
        "CAPABILITIES:\n"
        "- Search leads globally via Google Maps, Workana, LinkedIn, Facebook\n"
        "- Market analysis with real competitive data\n"
        "- Support any niche, any country, any language\n\n"
        "STRICT RULES:\n"
        "- NEVER assume country = Brazil. Always detect or ask.\n"
        "- NEVER invent data. Only use real scraper output.\n"
        "- If nicho, pais, or quantidade are unclear, ask before proceeding.\n"
        "- If cidade is not specified, pass null for national-scope search.\n"
        "- If the user mentions a region (e.g., 'nordeste', 'south'), set the estado parameter.\n"
        "- When user asks for Workana/freelance jobs, set fonte='workana'.\n"
        "- Be concise. No filler text. Every sentence must add value.\n\n"
        f"USER CONTEXT: {total} leads in dashboard, {conv_rate}% conversion rate. "
        f"{credit_context} {prioritization}"
    )


def _generate_conversational_reply(
    db: Session,
    user: User,
    user_message: str,
    metrics: dict,
    prioritization: str,
) -> str:
    client = _openai_client()
    if client is None:
        return "Please configure your OpenAI API key to enable AI-powered responses."

    history = _recent_messages_for_llm(db, user, limit=10)
    system = _build_system_prompt(metrics, prioritization, user=user)
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.4,
            max_tokens=400,
            messages=messages,
        )
        content = (completion.choices[0].message.content if completion.choices else "").strip()
        return content or "Please configure your OpenAI API key to enable AI-powered responses."
    except Exception:
        return "Please configure your OpenAI API key to enable AI-powered responses."


def handle_chat(db: Session, user: User, message: str, confirm_execution: bool) -> dict:
    if str(message or "").strip().lower() == "/clear":
        deleted = delete_messages(db, user)
        return {
            "intent": "clear",
            "requires_confirmation": False,
            "deleted": deleted,
            "assistant_message": None,
            "user_message": None,
        }

    user_message = _save_message(db, user=user, role=MessageRole.user, content=message)

    metrics = quick_metrics(db, user)
    prioritization = _build_prioritization_hint(db, user)

    client = _openai_client()
    if client is None:
        reply = "Please configure your OpenAI API key to enable AI-powered responses."
        logger.info("[AI ORCHESTRATOR] Intent: assistant | Args: N/A | Country: N/A | City: N/A | Qty: N/A | Status: no_api_key")
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=reply,
            metadata={"intent": "assistant", "requires_confirmation": False},
        )
        return {
            "intent": "assistant",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # Charge for the AI message
    try:
        consume_ai_message(db, user)
    except HTTPException:
        reply = (
            "Seus créditos acabaram. Para continuar usando o LeadAI Global, "
            "compre mais créditos ou faça upgrade do seu plano."
        )
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=reply,
            metadata={"intent": "credits_exhausted", "requires_confirmation": False},
        )
        return {
            "intent": "credits_exhausted",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # Build messages with history
    history = _recent_messages_for_llm(db, user)
    system_prompt = _build_system_prompt(metrics, prioritization, user=user)
    llm_messages = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(history)
    llm_messages.append({"role": "user", "content": message})

    # Call OpenAI with function calling
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.15,
            messages=llm_messages,
            tools=TOOLS,
            tool_choice="auto",
        )
    except Exception as exc:
        logger.error("[AI ORCHESTRATOR] OpenAI call failed: %s", exc)
        reply = _generate_conversational_reply(db, user, message, metrics, prioritization)
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=reply,
            metadata={"intent": "assistant", "requires_confirmation": False},
        )
        return {
            "intent": "assistant",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    response_message = completion.choices[0].message if completion.choices else None
    tool_calls = response_message.tool_calls if response_message else None

    # No tool calls — pure conversation
    if not tool_calls:
        reply = (response_message.content or "").strip() if response_message else ""
        if not reply:
            reply = _generate_conversational_reply(db, user, message, metrics, prioritization)
        logger.info("[AI ORCHESTRATOR] Intent: assistant | Args: N/A | Country: N/A | City: N/A | Qty: N/A | Status: conversational")
        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=reply,
            metadata={"intent": "assistant", "requires_confirmation": False},
        )
        return {
            "intent": "assistant",
            "requires_confirmation": False,
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    # Process the first tool call
    tool_call = tool_calls[0]
    fn_name = tool_call.function.name
    try:
        fn_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        fn_args = {}

    if fn_name == "buscar_leads":
        nicho = str(fn_args.get("nicho", "")).strip()
        pais = str(fn_args.get("pais", "")).strip()
        cidade = fn_args.get("cidade") or None
        quantidade = _coerce_quantity(fn_args.get("quantidade"))

        logger.info(
            "[AI ORCHESTRATOR] Intent: scrape | Args: %s | Country: %s | City: %s | Qty: %d | Status: requested",
            json.dumps(fn_args, ensure_ascii=False), pais, cidade, quantidade,
        )

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
            # Send tool result back to model to get a natural confirmation prompt
            followup_messages = llm_messages + [
                response_message.model_dump(),
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "status": "awaiting_confirmation",
                        "message": f"The user must confirm before executing. Summarize: nicho={nicho}, cidade={city_label}, pais={pais}, quantidade={quantidade}. Ask for confirmation.",
                    }),
                },
            ]
            try:
                confirm_completion = client.chat.completions.create(
                    model=settings.openai_model,
                    temperature=0.3,
                    max_tokens=300,
                    messages=followup_messages,
                )
                confirm_text = (confirm_completion.choices[0].message.content or "").strip() if confirm_completion.choices else ""
            except Exception:
                confirm_text = ""
            if not confirm_text:
                confirm_text = (
                    f"Confirm starting real scraping? "
                    f"Niche: {nicho}, City: {city_label}, Country: {pais}, Quantity: {quantidade} leads."
                )

            assistant_message = _save_message(
                db, user=user, role=MessageRole.assistant, content=confirm_text,
                metadata={"intent": "scrape", "requires_confirmation": True, "parsed": parsed},
            )
            return {
                "intent": "scrape",
                "requires_confirmation": True,
                "parsed_request": parsed,
                "assistant_message": _message_to_dict(assistant_message),
                "user_message": _message_to_dict(user_message),
            }

        # Execute scrape
        task = _create_task(
            db, user, task_type=TaskType.scraping, prompt=message,
            parsed_payload=parsed, requested_quantity=quantidade,
        )
        async_job = run_scrape_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info(
            "[AI ORCHESTRATOR] Intent: scrape | Args: %s | Country: %s | City: %s | Qty: %d | Status: executing",
            json.dumps(fn_args, ensure_ascii=False), pais, cidade, quantidade,
        )

        # Get natural response from model
        exec_messages = llm_messages + [
            response_message.model_dump(),
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": "started",
                    "task_id": str(task.id),
                    "message": f"Scraping task started for {quantidade} {nicho} leads in {cidade or 'national'}, {pais}.",
                }),
            },
        ]
        try:
            exec_completion = client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.3,
                max_tokens=300,
                messages=exec_messages,
            )
            exec_text = (exec_completion.choices[0].message.content or "").strip() if exec_completion.choices else ""
        except Exception:
            exec_text = ""
        if not exec_text:
            exec_text = "Search started. I'll update the progress and insert only real leads into your dashboard."

        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=exec_text,
            task_id=task.id,
            metadata={"intent": "scrape", "requires_confirmation": False, "task_id": str(task.id)},
        )
        return {
            "intent": "scrape",
            "requires_confirmation": False,
            "parsed_request": parsed,
            "task": _task_to_dict(task),
            "assistant_message": _message_to_dict(assistant_message),
            "user_message": _message_to_dict(user_message),
        }

    if fn_name == "analisar_mercado":
        nicho = str(fn_args.get("nicho", "")).strip()
        pais = str(fn_args.get("pais", "")).strip()
        cidade = fn_args.get("cidade") or None

        logger.info(
            "[AI ORCHESTRATOR] Intent: market | Args: %s | Country: %s | City: %s | Qty: 1 | Status: requested",
            json.dumps(fn_args, ensure_ascii=False), pais, cidade,
        )

        parsed = {
            "nicho": nicho,
            "cidade": cidade or pais,
            "pais": pais,
        }

        assert_external_query_quota(user, 1)

        if not confirm_execution:
            city_label = "Nacional" if cidade is None else cidade
            followup_messages = llm_messages + [
                response_message.model_dump(),
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "status": "awaiting_confirmation",
                        "message": f"The user must confirm. Summarize: market analysis for nicho={nicho}, cidade={city_label}, pais={pais}. Ask for confirmation.",
                    }),
                },
            ]
            try:
                confirm_completion = client.chat.completions.create(
                    model=settings.openai_model,
                    temperature=0.3,
                    max_tokens=300,
                    messages=followup_messages,
                )
                confirm_text = (confirm_completion.choices[0].message.content or "").strip() if confirm_completion.choices else ""
            except Exception:
                confirm_text = ""
            if not confirm_text:
                confirm_text = (
                    f"Confirm generating a market intelligence report with real external data? "
                    f"Niche: {nicho}, City: {city_label}, Country: {pais}."
                )

            assistant_message = _save_message(
                db, user=user, role=MessageRole.assistant, content=confirm_text,
                metadata={"intent": "market", "requires_confirmation": True, "parsed": parsed},
            )
            return {
                "intent": "market",
                "requires_confirmation": True,
                "parsed_request": parsed,
                "assistant_message": _message_to_dict(assistant_message),
                "user_message": _message_to_dict(user_message),
            }

        # Execute market analysis
        task = _create_task(
            db, user, task_type=TaskType.market_intelligence, prompt=message,
            parsed_payload=parsed, requested_quantity=1,
        )
        async_job = run_market_task.delay(str(task.id))
        task.celery_task_id = async_job.id
        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info(
            "[AI ORCHESTRATOR] Intent: market | Args: %s | Country: %s | City: %s | Qty: 1 | Status: executing",
            json.dumps(fn_args, ensure_ascii=False), pais, cidade,
        )

        exec_messages = llm_messages + [
            response_message.model_dump(),
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": "started",
                    "task_id": str(task.id),
                    "message": f"Market analysis started for {nicho} in {cidade or 'national'}, {pais}.",
                }),
            },
        ]
        try:
            exec_completion = client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.3,
                max_tokens=300,
                messages=exec_messages,
            )
            exec_text = (exec_completion.choices[0].message.content or "").strip() if exec_completion.choices else ""
        except Exception:
            exec_text = ""
        if not exec_text:
            exec_text = "Market analysis started. I'll return opportunity scores and risks based on real data."

        assistant_message = _save_message(
            db, user=user, role=MessageRole.assistant, content=exec_text,
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

    # Unknown tool call — treat as conversation
    logger.warning("[AI ORCHESTRATOR] Unknown tool call: %s", fn_name)
    reply = (response_message.content or "").strip() if response_message else ""
    if not reply:
        reply = _generate_conversational_reply(db, user, message, metrics, prioritization)
    assistant_message = _save_message(
        db, user=user, role=MessageRole.assistant, content=reply,
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


def delete_messages(db: Session, user: User) -> int:
    deleted = (
        db.query(AIMessage)
        .filter(AIMessage.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted)


def get_task(db: Session, user: User, task_id: str) -> dict:
    parsed_task_id = _canonical_id(task_id)
    if not parsed_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task id")

    task = db.query(AITask).filter(AITask.id == parsed_task_id, AITask.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return _task_to_dict(task)
