"""
forge/main.py

FastAPI application factory + startup/shutdown lifecycle hooks.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from forge.api.routes import router
from forge.api.v1.eval import router as eval_router
from forge.api.v1.rag import router as rag_router
from forge.core.config import settings
from forge.core.database import create_all_tables
from forge.modules.loader import ModuleLoader

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings.ensure_dirs()
    settings.get_or_create_api_key()
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

    app.include_router(router, prefix="/api")
    app.include_router(rag_router, prefix="/api")
    app.include_router(eval_router, prefix="/api")

    @app.on_event("startup")
    async def _startup():
        await create_all_tables()
        logger.info("Database tables ready")

        loader = ModuleLoader()
        loaded_for_registry = await loader.load_all(
            __import__("forge.agent.tools.registry", fromlist=["*"])
        )
        logger.info(
            "Loaded modules into internal registry: %s", loaded_for_registry or "none"
        )

        try:
            from forge.tool_server import mcp

            loaded_for_mcp = await loader.load_all(mcp)
            logger.info(
                "Loaded modules into FastMCP server: %s", loaded_for_mcp or "none"
            )
        except Exception as exc:
            logger.debug("FastMCP module loading skipped: %s", exc)

    @app.get("/health", tags=["system"], include_in_schema=False)
    async def root_health():
        return {"status": "ok"}

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

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
