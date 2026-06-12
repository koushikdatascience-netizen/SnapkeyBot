from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, integrations, operator, tools, voice
from app.config import get_settings
from app.database import create_tables
from app.schemas import AppConfigResponse
from app.services.telegram import telegram_webhook_ready
from app.services.elevenlabs import live_agent_ready, voice_ready


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_tables()
    yield


app = FastAPI(title="Snapkey Assistant API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(auth.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(operator.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/deployment-info")
async def deployment_info() -> dict[str, str]:
    return {
        "app": "snapkey-assistant",
        "release": "meeting-presenter-v1",
        "presenter_path": "/presenter?demo_session=meeting1",
        "director_path": "/director",
    }


@app.get("/api/config", response_model=AppConfigResponse)
async def app_config() -> AppConfigResponse:
    settings = get_settings()
    return AppConfigResponse(
        concierge_mode=settings.concierge_mode,
        concierge_ready=await telegram_webhook_ready() if settings.concierge_mode else True,
        max_upload_bytes=settings.max_upload_bytes,
        voice_ready=voice_ready(),
        live_agent_ready=live_agent_ready(),
        monitoring_camera_urls=[
            url.strip() for url in settings.monitoring_camera_urls.split(",") if url.strip()
        ][:3],
        monitoring_screen_url=settings.monitoring_screen_url,
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/director", include_in_schema=False)
async def director() -> FileResponse:
    return FileResponse(static_dir / "director.html")


@app.get("/presenter", include_in_schema=False)
async def presenter() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/live", include_in_schema=False)
async def live() -> FileResponse:
    return FileResponse(static_dir / "index.html")
