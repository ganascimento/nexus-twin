from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Truck


class TruckRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> list[Truck]:
        result = await self._session.execute(select(Truck))
        return result.scalars().all()

    async def get_by_id(self, id: str) -> Truck | None:
        result = await self._session.execute(select(Truck).where(Truck.id == id))
        return result.scalar_one_or_none()

    async def get_by_factory(self, factory_id: str) -> list[Truck]:
        result = await self._session.execute(
            select(Truck).where(Truck.factory_id == factory_id)
        )
        return result.scalars().all()

    async def create(self, data: dict) -> Truck:
        truck = Truck(**data)
        self._session.add(truck)
        await self._session.flush()
        await self._session.refresh(truck)
        return truck

    async def delete(self, id: str) -> None:
        await self._session.execute(delete(Truck).where(Truck.id == id))

    async def update_status(self, id: str, status: str) -> None:
        await self._session.execute(
            update(Truck).where(Truck.id == id).values(status=status)
        )

    async def try_lock_for_evaluation(self, truck_id: str) -> bool:
        result = await self._session.execute(
            select(Truck)
            .where(Truck.id == truck_id, Truck.status == "idle")
            .with_for_update(skip_locked=True)
        )
        truck = result.scalar_one_or_none()
        if truck is None:
            return False
        truck.status = "evaluating"
        await self._session.flush()
        return True

    async def update_position(self, id: str, lat: float, lng: float) -> None:
        await self._session.execute(
            update(Truck).where(Truck.id == id).values(current_lat=lat, current_lng=lng)
        )

    async def update_degradation(
        self, id: str, degradation: float, breakdown_risk: float
    ) -> None:
        await self._session.execute(
            update(Truck)
            .where(Truck.id == id)
            .values(degradation=degradation, breakdown_risk=breakdown_risk)
        )

    async def set_cargo(self, id: str, cargo: dict | None) -> None:
        await self._session.execute(
            update(Truck).where(Truck.id == id).values(cargo=cargo)
        )

    async def set_active_route(self, id: str, route_id) -> None:
        await self._session.execute(
            update(Truck).where(Truck.id == id).values(active_route_id=route_id)
        )

    async def set_maintenance_info(self, truck_id: str, start_tick: int, duration_ticks: int) -> None:
        await self._session.execute(
            update(Truck)
            .where(Truck.id == truck_id)
            .values(maintenance_start_tick=start_tick, maintenance_duration_ticks=duration_ticks)
        )

    async def clear_maintenance_info(self, truck_id: str) -> None:
        await self._session.execute(
            update(Truck)
            .where(Truck.id == truck_id)
            .values(maintenance_start_tick=None, maintenance_duration_ticks=None)
        )

    async def get_idle_by_factory(self, factory_id: str) -> Truck | None:
        result = await self._session.execute(
            select(Truck).where(
                Truck.factory_id == factory_id,
                Truck.status == "idle",
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_nearest_idle_third_party(self, lat: float, lng: float) -> Truck | None:
        distance = func.sqrt(
            func.pow(Truck.current_lat - lat, 2) + func.pow(Truck.current_lng - lng, 2)
        )
        result = await self._session.execute(
            select(Truck)
            .where(Truck.truck_type == "terceiro", Truck.status == "idle")
            .order_by(distance)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_idle_third_party_for_load(
        self,
        quantity_tons: float,
        ref_lat: float,
        ref_lng: float,
        exclude_id: str | None = None,
        exclude_ids: set | None = None,
    ) -> Truck | None:
        stmt = select(Truck).where(
            Truck.truck_type == "terceiro",
            Truck.status == "idle",
            Truck.capacity_tons >= quantity_tons,
        )
        if exclude_id is not None:
            stmt = stmt.where(Truck.id != exclude_id)
        if exclude_ids:
            stmt = stmt.where(Truck.id.notin_(list(exclude_ids)))

        result = await self._session.execute(stmt)
        candidates = list(result.scalars().all())
        if not candidates:
            return None

        def score(truck: Truck) -> tuple[float, float]:
            waste = truck.capacity_tons - quantity_tons
            dist = (truck.current_lat - ref_lat) ** 2 + (truck.current_lng - ref_lng) ** 2
            return (waste, dist)

        candidates.sort(key=score)
        return candidates[0]

    async def get_all_in_maintenance(self) -> list[Truck]:
        result = await self._session.execute(
            select(Truck).where(Truck.status == "maintenance")
        )
        return result.scalars().all()
