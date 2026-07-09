import pathlib

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.db import init_db
from core.connectors.copilot import router as mcp_router
from core.routes.curation import router as curation_router
from core.routes.health import router as health_router
from core.routes.ingest import router as ingest_router
from core.routes.root import router as root_router
from core.routes.search import router as search_router

_UI_DIR = pathlib.Path(__file__).parent.parent.parent / "ui"

app = FastAPI(title="memward API")


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(root_router)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(search_router)
app.include_router(curation_router)
app.include_router(mcp_router)


@app.get("/ui", include_in_schema=False)
async def serve_ui() -> FileResponse:
    return FileResponse(_UI_DIR / "index.html", media_type="text/html")