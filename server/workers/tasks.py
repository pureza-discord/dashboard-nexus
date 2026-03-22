from datetime import datetime

from celery import states # type: ignore

from server.core.database import session_scope # type: ignore
from server.db.models import AIMessage, AITask, MessageRole, TaskStatus, User # type: ignore
from server.modules.billing.service import consume_external_queries, consume_leads # type: ignore
from server.modules.leads.service import upsert_leads # type: ignore
from server.modules.market_intelligence_service.service import MarketRequest, run_market_analysis # type: ignore
from server.modules.scraper_service.service import ScrapeRequest, collect_leads # type: ignore
from server.workers.celery_app import celery_app # type: ignore


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
        error_str = str(error)
        task.status = TaskStatus.failed
        task.error_message = error_str[:2000] # type: ignore
        task.completed_at = _now()
        task.updated_at = _now()
        task.progress = max(task.progress, 100)
        payload = dict(task.result_payload or {})
        payload["stage_message"] = "Falha na execução"
        task.result_payload = payload
        db.add(task)

        msg = AIMessage(
            user_id=task.user_id,
            task_id=task.id,
            role=MessageRole.assistant,
            content=f"A tarefa falhou: {error}",
            message_metadata={"event": "task_failed"},
        )
        db.add(msg)


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

        msg = AIMessage(
            user_id=task.user_id,
            task_id=task.id,
            role=MessageRole.assistant,
            content=message,
            message_metadata={"event": "task_completed", "result": result_payload},
        )
        db.add(msg)


@celery_app.task(name="server.workers.tasks.run_scrape_task", bind=True)
def run_scrape_task(self, task_id: str):
    task, user = _mark_task_running(task_id)
    if not task or not user:
        self.update_state(state=states.FAILURE, meta={"error": "Task or user not found"})
        return {"ok": False, "error": "Task or user not found"}

    nicho = str(task.parsed_payload.get("nicho") or "").strip()
    pais = str(task.parsed_payload.get("pais") or "").strip()
    if not nicho:
        _mark_task_failed(task_id, "Niche (nicho) is required but was not provided.")
        return {"ok": False, "error": "Missing nicho"}
    if not pais:
        _mark_task_failed(task_id, "Country (pais) is required but was not provided.")
        return {"ok": False, "error": "Missing pais"}

    request = ScrapeRequest(
        nicho=nicho,
        cidade=(str(task.parsed_payload.get("cidade")).strip() if task.parsed_payload.get("cidade") else None),
        pais=pais,
        quantidade=int(task.parsed_payload.get("quantidade") or max(task.requested_quantity, 50)),
        source=task.parsed_payload.get("source", "google_maps"),
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

            payload = {
                "request": task.parsed_payload,
                "inserted": insertion["inserted"],
                "duplicates": insertion["duplicates"],
                "total_received": insertion["total_received"],
            }

        _mark_task_completed(
            task_id,
            completed_quantity=insertion["inserted"],
            result_payload=payload,
            message=(
                f"Busca finalizada: {insertion['inserted']} leads novos adicionados "
                f"(duplicados ignorados: {insertion['duplicates']})."
            ),
        )

        return {"ok": True, **payload}
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

        with session_scope() as db:
            db_user = db.query(User).filter(User.id == user.id).first()
            if not db_user:
                raise RuntimeError("User disappeared during market task")

            market_nicho = str(task.parsed_payload.get("nicho") or "").strip()
            market_pais = str(task.parsed_payload.get("pais") or "").strip()
            if not market_nicho or not market_pais:
                raise RuntimeError("Niche and country are required for market analysis.")
            request = MarketRequest(
                nicho=market_nicho,
                cidade=str(task.parsed_payload.get("cidade") or market_pais),
                pais=market_pais,
            )
            report = run_market_analysis(db, db_user, request)
            consume_external_queries(db, db_user, 1)

        _update_task_progress(task_id, 95, "Gerando relatório estruturado")
        self.update_state(state="PROGRESS", meta={"progress": 95})

        _mark_task_completed(
            task_id,
            completed_quantity=1,
            result_payload=report,
            message=(
                "Relatório de mercado pronto. "
                f"Score de mercado: {report['market_score']} | Oportunidade: {report['opportunity_index']}"
            ),
        )

        return {"ok": True, **report}
    except Exception as exc:
        _mark_task_failed(task_id, str(exc))
        raise

