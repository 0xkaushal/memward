import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.db import init_db
from core.connectors.copilot import router as mcp_router
from core.routes.curation import router as curation_router
from core.routes.health import router as health_router
from core.routes.ingest import router as ingest_router
from core.routes.root import router as root_router
from core.routes.search import router as search_router

_UI_DIST = pathlib.Path(__file__).parent.parent.parent / "ui" / "dist"

app = FastAPI(title="memward API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(root_router)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(search_router)
app.include_router(curation_router)
app.include_router(mcp_router)

# Serve React build (production). For dev, run `npm run dev` in ui/ instead.
if _UI_DIST.exists():
    app.mount("/ui", StaticFiles(directory=_UI_DIST, html=True), name="ui")