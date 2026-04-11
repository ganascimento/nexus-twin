from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Route


class RouteRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, data: dict) -> Route:
        route = Route(**data)
        self._session.add(route)
        await self._session.flush()
        await self._session.refresh(route)
        return route

    async def get_by_id(self, id: UUID) -> Route | None:
        result = await self._session.execute(select(Route).where(Route.id == id))
        return result.scalar_one_or_none()

    async def get_active_by_truck(self, truck_id: str) -> Route | None:
        result = await self._session.execute(
            select(Route).where(Route.truck_id == truck_id, Route.status == "active")
        )
        return result.scalar_one_or_none()

    async def update_eta_ticks(self, route_id: UUID, eta_ticks: int) -> None:
        await self._session.execute(
            update(Route).where(Route.id == route_id).values(eta_ticks=eta_ticks)
        )

    async def update_status(
        self, route_id: UUID, status: str, completed_at: datetime | None = None
    ) -> None:
        values = {"status": status}
        if completed_at is not None:
            values["completed_at"] = completed_at
        await self._session.execute(
            update(Route).where(Route.id == route_id).values(**values)
        )
