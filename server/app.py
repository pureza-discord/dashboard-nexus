from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from server.api.system_router import router as system_router
from server.core.database import SessionLocal, init_db
from server.core.settings import get_settings
from server.modules.ai_orchestrator.router import router as ai_router
from server.modules.analytics.router import router as analytics_router
from server.modules.auth.router import router as auth_router
from server.modules.auth.service import bootstrap_admin_user
from server.modules.billing.router import router as billing_router
from server.modules.leads.router import router as leads_router
from server.modules.market_intelligence_service.router import router as market_router
from server.modules.users.router import router as users_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        bootstrap_admin_user(db)
    finally:
        db.close()


app.include_router(system_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(billing_router)
app.include_router(leads_router)
app.include_router(analytics_router)
app.include_router(ai_router)
app.include_router(market_router)


dist_path = Path(settings.frontend_dist)

if dist_path.exists():
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api"):
            return HTMLResponse("Not found", status_code=404)

        file_path = dist_path / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))

        index = dist_path / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text(encoding="utf-8"))

        return HTMLResponse("<h1>Frontend not built</h1>", status_code=500)
else:

    @app.get("/")
    def root():
        return {
            "service": settings.app_name,
            "status": "ok",
            "docs": "/docs" if settings.environment != "production" else None,
            "frontend": "Build frontend with: cd frontend && npm run build",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.app:app", host=settings.api_host, port=settings.api_port, reload=True)
