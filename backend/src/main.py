import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes.chaos import router as chaos_router
from src.api.routes.decisions import router as decisions_router
from src.api.routes.exports import router as exports_router
from src.api.routes.factories import router as factories_router
from src.api.routes.materials import router as materials_router
from src.api.routes.reports import router as reports_router
from src.api.routes.simulation import router as simulation_router
from src.api.routes.stores import router as stores_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.trucks import router as trucks_router
from src.api.routes.warehouses import router as warehouses_router
from src.api.routes.world import router as world_router
from src.api.websocket import ConnectionManager, redis_subscriber, websocket_endpoint


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _configure_logging() -> None:
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nexus Twin backend starting up")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    app.state.redis = aioredis.from_url(redis_url)
    app.state.ws_manager = ConnectionManager()
    app.state.redis_subscriber_task = asyncio.create_task(
        redis_subscriber(app.state.redis, app.state.ws_manager)
    )

    from src.database.session import _get_engine, AsyncSessionLocal
    from src.services.simulation import SimulationService
    from src.services.world_state import WorldStateService
    from src.simulation.engine import SimulationEngine

    _get_engine()

    world_state_service = WorldStateService(AsyncSessionLocal())
    engine = SimulationEngine(world_state_service, app.state.redis, AsyncSessionLocal)
    app.state.simulation_service = SimulationService(engine)

    yield
    if app.state.simulation_service.is_running:
        await app.state.simulation_service.stop()
    app.state.redis_subscriber_task.cancel()
    try:
        await app.state.redis_subscriber_task
    except asyncio.CancelledError:
        pass
    await app.state.redis.close()
    logger.info("Nexus Twin backend shutting down")


app = FastAPI(title="Nexus Twin", lifespan=lifespan)

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


API_V1_PREFIX = "/api/v1"

app.include_router(simulation_router, prefix=API_V1_PREFIX)
app.include_router(world_router, prefix=API_V1_PREFIX)
app.include_router(materials_router, prefix=API_V1_PREFIX)
app.include_router(factories_router, prefix=API_V1_PREFIX)
app.include_router(warehouses_router, prefix=API_V1_PREFIX)
app.include_router(stores_router, prefix=API_V1_PREFIX)
app.include_router(trucks_router, prefix=API_V1_PREFIX)
app.include_router(chaos_router, prefix=API_V1_PREFIX)
app.include_router(decisions_router, prefix=API_V1_PREFIX)
app.include_router(reports_router, prefix=API_V1_PREFIX)
app.include_router(exports_router, prefix=API_V1_PREFIX)
app.include_router(tasks_router, prefix=API_V1_PREFIX)

app.add_api_websocket_route("/ws", websocket_endpoint)
