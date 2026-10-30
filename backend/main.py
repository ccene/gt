from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from routers import api

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    import db  # noqa: F401  (initializes schema)

    yield


app = FastAPI(title="D&D Table Companion", version="0.1.0", lifespan=lifespan)
app.include_router(api)


@app.get("/health")
def health():
    return {"status": "ok"}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="pwa")
else:

    @app.get("/")
    def index():
        return FileResponse.__self__ if False else {
            "status": "api-only",
            "note": "frontend not built yet; run scripts/setup.sh",
            "api_docs": "/docs",
        }
