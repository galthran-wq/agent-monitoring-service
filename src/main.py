import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.api.router import router
from src.config import settings
from src.core.exceptions import register_exception_handlers
from src.core.middleware import register_middleware
from src.exporters import get_configured_exporters
from src.services.monitor import AgentMonitor
from src.sources import get_configured_sources

logger = structlog.get_logger()


def configure_logging() -> None:
    log_level: int = getattr(logging, settings.log_level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("startup", app_name=settings.app_name)

    sources = get_configured_sources()
    exporters = get_configured_exporters()
    logger.info(
        "monitor_starting",
        sources=[s.name for s in sources],
        exporters=[e.name for e in exporters],
    )

    monitor = AgentMonitor(sources=sources, exporters=exporters)
    app.state.monitor = monitor
    monitor_task = asyncio.create_task(monitor.run())

    yield

    monitor_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await monitor_task
    logger.info("shutdown", app_name=settings.app_name)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    register_middleware(application)
    register_exception_handlers(application)
    application.include_router(router)
    if settings.metrics_enabled:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            excluded_handlers=["/health", "/ready", "/metrics"],
        ).instrument(application).expose(application)
    return application


app = create_app()
