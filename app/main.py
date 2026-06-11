from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, operator, tools
from app.config import get_settings
from app.database import create_tables
from app.schemas import AppConfigResponse
from app.services.telegram import telegram_webhook_ready


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_tables()
    yield


app = FastAPI(title="Snapkey Assistant API", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(operator.router, prefix="/api")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config", response_model=AppConfigResponse)
async def app_config() -> AppConfigResponse:
    settings = get_settings()
    return AppConfigResponse(
        concierge_mode=settings.concierge_mode,
        concierge_ready=await telegram_webhook_ready() if settings.concierge_mode else True,
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")
