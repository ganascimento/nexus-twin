import uuid

from src.enums import TruckStatus
from src.services import ConflictError, NotFoundError
from src.world.physics import calculate_maintenance_ticks


class TruckService:
    def __init__(self, repo, publisher):
        self._repo = repo
        self._publisher = publisher

    async def list_trucks(self):
        return await self._repo.get_all()

    async def get_truck(self, id: str):
        truck = await self._repo.get_by_id(id)
        if truck is None:
            raise NotFoundError(f"Truck '{id}' not found")
        return truck

    async def create_truck(self, data: dict):
        payload = data.copy()
        if "id" not in payload:
            payload["id"] = f"truck-{uuid.uuid4().hex[:8]}"
        payload["status"] = TruckStatus.IDLE.value
        payload["degradation"] = 0.0
        payload["breakdown_risk"] = 0.0
        if "lat" in payload:
            lat = payload.pop("lat")
            payload.setdefault("base_lat", lat)
            payload.setdefault("current_lat", lat)
        if "lng" in payload:
            lng = payload.pop("lng")
            payload.setdefault("base_lng", lng)
            payload.setdefault("current_lng", lng)
        payload.pop("name", None)
        return await self._repo.create(payload)

    async def delete_truck(self, id: str) -> None:
        truck = await self._repo.get_by_id(id)
        if truck is None:
            raise NotFoundError(f"Truck '{id}' not found")
        if truck.status == TruckStatus.IN_TRANSIT.value:
            await self._publisher.publish_event(
                "truck_deleted_in_transit", {"truck_id": id, "cargo": truck.cargo}
            )
        await self._repo.delete(id)

    async def try_lock_for_evaluation(self, truck_id: str) -> bool:
        return await self._repo.try_lock_for_evaluation(truck_id)

    async def assign_route(self, truck_id: str, route_id: str, cargo: dict) -> None:
        truck = await self.get_truck(truck_id)
        if truck.status not in (TruckStatus.IDLE.value, TruckStatus.EVALUATING.value):
            raise ConflictError(f"Truck '{truck_id}' is not available (status={truck.status})")
        await self._repo.set_cargo(truck_id, cargo)
        await self._repo.set_active_route(truck_id, route_id)
        await self._repo.update_status(truck_id, TruckStatus.IN_TRANSIT.value)

    async def complete_route(self, truck_id: str) -> None:
        truck = await self.get_truck(truck_id)
        if truck.status != TruckStatus.IN_TRANSIT.value:
            raise ConflictError(f"Truck '{truck_id}' is not in transit (status={truck.status})")
        await self._repo.set_cargo(truck_id, None)
        await self._repo.set_active_route(truck_id, None)
        await self._repo.update_status(truck_id, TruckStatus.IDLE.value)
        await self._publisher.publish_event(
            "truck_arrived", {"truck_id": truck_id}
        )

    async def interrupt_route(self, truck_id: str, reason: str) -> None:
        truck = await self.get_truck(truck_id)
        if truck.status != TruckStatus.IN_TRANSIT.value:
            raise ConflictError(f"Truck '{truck_id}' is not in transit (status={truck.status})")
        await self._repo.set_active_route(truck_id, None)
        await self._repo.update_status(truck_id, TruckStatus.IDLE.value)
        await self._publisher.publish_event(
            "truck_route_interrupted", {"truck_id": truck_id, "reason": reason}
        )

    async def schedule_maintenance(self, truck_id: str, current_tick: int = 0) -> None:
        truck = await self.get_truck(truck_id)
        if truck.status == TruckStatus.IN_TRANSIT.value:
            raise ConflictError(f"Truck '{truck_id}' is in transit, cannot schedule maintenance")
        duration = calculate_maintenance_ticks(truck.degradation)
        await self._repo.update_status(truck_id, TruckStatus.MAINTENANCE.value)
        await self._repo.update_degradation(truck_id, 0.0, 0.0)
        await self._repo.set_maintenance_info(truck_id, current_tick, duration)
        await self._publisher.publish_event(
            "truck_maintenance_started",
            {"truck_id": truck_id, "duration_ticks": duration},
        )
