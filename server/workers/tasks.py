from __future__ import annotations

from datetime import datetime

from celery import states

from server.core.database import session_scope
from server.db.models import AITask, Message, MessageRole, TaskStatus, User
from server.modules.billing.service import consume_external_queries, consume_leads
from server.modules.leads.service import upsert_leads
from server.modules.market_intelligence_service.service import MarketRequest, run_market_analysis
from server.modules.scraper_service.service import ScrapeRequest, collect_leads
from server.workers.celery_app import celery_app


def _now() -> datetime:
    return datetime.utcnow()


def _task_key(task_id: str) -> str:
    return str(task_id).strip()


def _update_task_progress(task_id: str, progress: int, stage_message: str) -> None:
    with session_scope() as db:
        task = db.query(AITask).filter(AITask.id == _task_key(task_id)).first()
        if not task:
            return
        task.progress = max(0, min(100, progress))
        payload = dict(task.result_payload or {})
        payload["stage_message"] = stage_message
        task.result_payload = payload
        task.updated_at = _now()
        db.add(task)


def _append_chat_message(task: AITask, content: str, tool_calls: list | dict | None = None) -> None:
    if not task.chat_id:
        return
    with session_scope() as db:
        msg = Message(
            chat_id=task.chat_id,
            role=MessageRole.assistant,
            content=content,
            tool_calls=tool_calls,
        )
        db.add(msg)


def _mark_task_running(task_id: str) -> tuple[AITask | None, User | None]:
    with session_scope() as db:
        task = db.query(AITask).filter(AITask.id == _task_key(task_id)).first()
        if not task:
            return None, None

        user = db.query(User).filter(User.id == task.user_id).first()
        if not user:
            return None, None

        task.status = TaskStatus.running
        task.progress = max(5, task.progress)
        task.started_at = _now()
        task.updated_at = _now()
        db.add(task)

        db.expunge(task)
        db.expunge(user)
        return task, user


def _mark_task_failed(task_id: str, error: str) -> None:
    with session_scope() as db:
        task = db.query(AITask).filter(AITask.id == _task_key(task_id)).first()
        if not task:
            return

        task.status = TaskStatus.failed
        task.error_message = error[:2000]
        task.completed_at = _now()
        task.updated_at = _now()
        task.progress = max(task.progress, 100)
        payload = dict(task.result_payload or {})
        payload["stage_message"] = "Falha na execucao"
        task.result_payload = payload
        db.add(task)

    _append_chat_message(
        task,
        f"A busca falhou: {error}",
        tool_calls={"event": "task_failed", "error": error[:400]},
    )


def _mark_task_completed(task_id: str, completed_quantity: int, result_payload: dict, message: str) -> None:
    with session_scope() as db:
        task = db.query(AITask).filter(AITask.id == _task_key(task_id)).first()
        if not task:
            return

        task.status = TaskStatus.completed
        task.progress = 100
        task.completed_quantity = max(0, completed_quantity)
        task.result_payload = result_payload
        task.completed_at = _now()
        task.updated_at = _now()
        db.add(task)

    _append_chat_message(
        task,
        message,
        tool_calls={"event": "task_completed", "result": result_payload},
    )


@celery_app.task(name="server.workers.tasks.run_scrape_task", bind=True)
def run_scrape_task(self, task_id: str):
    task, user = _mark_task_running(task_id)
    if not task or not user:
        self.update_state(state=states.FAILURE, meta={"error": "Task or user not found"})
        return {"ok": False, "error": "Task or user not found"}

    payload = task.parsed_payload or {}
    nicho = str(payload.get("niche") or payload.get("nicho") or "").strip()
    pais = str(payload.get("country") or payload.get("pais") or "").strip()
    cidade_raw = payload.get("city") if "city" in payload else payload.get("cidade")
    cidade = str(cidade_raw).strip() if cidade_raw else None
    quantidade = int(payload.get("quantity") or payload.get("quantidade") or max(task.requested_quantity, 5))

    if not nicho:
        _mark_task_failed(task_id, "Nicho obrigatorio para iniciar busca")
        return {"ok": False, "error": "Missing niche"}
    if not pais:
        _mark_task_failed(task_id, "Pais obrigatorio para iniciar busca")
        return {"ok": False, "error": "Missing country"}

    request = ScrapeRequest(
        nicho=nicho,
        cidade=cidade,
        pais=pais,
        quantidade=max(1, min(quantidade, 100)),
    )

    def progress_callback(progress: int, stage_message: str) -> None:
        _update_task_progress(task_id, progress, stage_message)
        self.update_state(state="PROGRESS", meta={"progress": progress, "message": stage_message})

    try:
        leads = collect_leads(request, progress=progress_callback)
        progress_callback(97, "Persistindo leads no banco")

        with session_scope() as db:
            db_user = db.query(User).filter(User.id == user.id).first()
            if not db_user:
                raise RuntimeError("User disappeared during task execution")

            insertion = upsert_leads(db, db_user, leads)
            consume_leads(db, db_user, insertion["inserted"])

            result_payload = {
                "request": payload,
                "inserted": insertion["inserted"],
                "duplicates": insertion["duplicates"],
                "total_received": insertion["total_received"],
            }

        parts = [f"Busca finalizada: {result_payload['inserted']} leads novos adicionados."]
        if result_payload["duplicates"] > 0:
            parts.append(f"{result_payload['duplicates']} leads duplicados ja existentes na sua conta foram ignorados.")
        if result_payload["inserted"] < quantidade:
            parts.append(
                f"Voce solicitou {quantidade}, mas apenas {result_payload['inserted']} leads ineditos foram encontrados "
                f"apos remover duplicatas da sua conta."
            )

        _mark_task_completed(
            task_id,
            completed_quantity=result_payload["inserted"],
            result_payload=result_payload,
            message=" ".join(parts),
        )

        return {"ok": True, **result_payload}
    except Exception as exc:
        _mark_task_failed(task_id, str(exc))
        raise


@celery_app.task(name="server.workers.tasks.run_market_task", bind=True)
def run_market_task(self, task_id: str):
    task, user = _mark_task_running(task_id)
    if not task or not user:
        self.update_state(state=states.FAILURE, meta={"error": "Task or user not found"})
        return {"ok": False, "error": "Task or user not found"}

    try:
        _update_task_progress(task_id, 20, "Consultando dados externos")
        self.update_state(state="PROGRESS", meta={"progress": 20})

        payload = task.parsed_payload or {}
        nicho = str(payload.get("niche") or payload.get("nicho") or "").strip()
        pais = str(payload.get("country") or payload.get("pais") or "Brasil").strip()
        cidade = str(payload.get("city") or payload.get("cidade") or pais).strip()

        with session_scope() as db:
            db_user = db.query(User).filter(User.id == user.id).first()
            if not db_user:
                raise RuntimeError("User disappeared during market task")

            request = MarketRequest(nicho=nicho or "negocios locais", cidade=cidade, pais=pais)
            report = run_market_analysis(db, db_user, request)
            consume_external_queries(db, db_user, 1)

        _update_task_progress(task_id, 95, "Gerando relatorio estruturado")
        self.update_state(state="PROGRESS", meta={"progress": 95})

        _mark_task_completed(
            task_id,
            completed_quantity=1,
            result_payload=report,
            message=(
                "Relatorio de mercado pronto. "
                f"Score de mercado: {report['market_score']} | Oportunidade: {report['opportunity_index']}"
            ),
        )

        return {"ok": True, **report}
    except Exception as exc:
        _mark_task_failed(task_id, str(exc))
        raise
