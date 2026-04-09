import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes.chaos import router as chaos_router
from src.api.routes.decisions import router as decisions_router
from src.api.routes.factories import router as factories_router
from src.api.routes.materials import router as materials_router
from src.api.routes.simulation import router as simulation_router
from src.api.routes.stores import router as stores_router
from src.api.routes.trucks import router as trucks_router
from src.api.routes.warehouses import router as warehouses_router
from src.api.routes.world import router as world_router


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

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _configure_logging() -> None:
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nexus Twin backend starting up")
    yield
    logger.info("Nexus Twin backend shutting down")


app = FastAPI(title="Nexus Twin", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
