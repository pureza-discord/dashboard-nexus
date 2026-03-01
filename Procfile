web: uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A server.workers.celery_app.celery_app worker --loglevel=info
