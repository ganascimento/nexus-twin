import asyncio
import os

from loguru import logger

from src.simulation.engine import SimulationEngine


class SimulationService:
    def __init__(self, engine: SimulationEngine):
        self._engine = engine
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._engine._running

    @property
    def current_tick(self) -> int:
        return self._engine._tick

    @property
    def tick_interval(self) -> float:
        return self._engine._tick_interval

    async def start(self) -> dict:
        if self._engine._running:
            return {"status": "already_running", "tick": self._engine._tick}
        self._task = asyncio.create_task(self._engine.start())
        logger.info("Simulation started")
        return {"status": "started", "tick": self._engine._tick}

    async def stop(self) -> dict:
        if not self._engine._running:
            return {"status": "already_stopped", "tick": self._engine._tick}
        self._engine.stop()
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Simulation stopped at tick {}", self._engine._tick)
        return {"status": "stopped", "tick": self._engine._tick}

    async def advance_tick(self) -> dict:
        await self._engine.advance_one_tick()
        return {"status": "advanced", "tick": self._engine._tick}

    def get_status(self) -> dict:
        return {
            "status": "running" if self._engine._running else "stopped",
            "current_tick": self._engine._tick,
            "tick_interval_seconds": self._engine._tick_interval,
        }

    def set_tick_interval(self, seconds: float) -> dict:
        min_interval = float(os.getenv("TICK_INTERVAL_SECONDS", "10.0"))
        if seconds < min_interval:
            seconds = min_interval
        self._engine._tick_interval = seconds
        return {"tick_interval_seconds": seconds}
