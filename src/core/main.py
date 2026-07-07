from fastapi import FastAPI

from core.routes.health import router as health_router
from core.routes.ingest import router as ingest_router
from core.routes.root import router as root_router
from core.routes.search import router as search_router

app = FastAPI(title="memward API")
app.include_router(root_router)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(search_router)