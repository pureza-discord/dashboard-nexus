import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from server.config import FRONTEND_DIST, ASSETS_DIR
from server.routes import auth, leads, analytics
from server.services.auth_service import init_users_table

init_users_table()

app = FastAPI(title="Nexus Leads Dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(analytics.router)

assets_path = Path(ASSETS_DIR)
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

dist_path = Path(FRONTEND_DIST)

if dist_path.exists():
    dist_assets = dist_path / "assets"
    if dist_assets.exists():
        app.mount("/static", StaticFiles(directory=str(dist_assets)), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = dist_path / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        index = dist_path / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Frontend not built. Run: cd frontend && npm run build</h1>", 500)
else:
    @app.get("/")
    async def no_frontend():
        return HTMLResponse(
            "<h1>Frontend not built</h1><p>Run: <code>cd frontend && npm install && npm run build</code></p>",
            500,
        )


if __name__ == "__main__":
    import uvicorn
    print("\n  Nexus Leads Dashboard: http://localhost:8000")
    print("  Login: admin / admin123\n")
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
