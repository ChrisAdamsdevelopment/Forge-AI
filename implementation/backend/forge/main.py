"""
forge/main.py

FastAPI application factory + startup/shutdown lifecycle hooks.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.api.routes import router
from forge.core.config import settings
from forge.core.database import create_all_tables

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings.ensure_dirs()
    api_key = settings.get_or_create_api_key()
    logger.info("Forge API starting on %s:%d", settings.host, settings.port)
    logger.info("API key stored at %s", settings.data_dir / "auth.key")

    app = FastAPI(
        title="Forge API",
        version="0.1.0",
        description="Self-hosted personal AI agent platform",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origins = list(settings.allowed_origins)
    if settings.enable_lan:
        # Allow any origin so LAN clients can connect
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    @app.on_event("startup")
    async def _startup():
        await create_all_tables()
        logger.info("Database tables ready")

    @app.get("/health", tags=["system"], include_in_schema=False)
    async def root_health():
        return {"status": "ok"}

    return app


app = create_app()


def run():
    import uvicorn
    uvicorn.run(
        "forge.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    run()
