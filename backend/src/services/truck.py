from src.services import NotFoundError


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
        payload["status"] = "idle"
        payload["degradation"] = 0.0
        return await self._repo.create(payload)

    async def delete_truck(self, id: str) -> None:
        truck = await self._repo.get_by_id(id)
        if truck is None:
            raise NotFoundError(f"Truck '{id}' not found")
        if truck.status == "in_transit":
            await self._publisher.publish_event(
                "truck_deleted_in_transit", {"truck_id": id, "cargo": truck.cargo}
            )
        await self._repo.delete(id)

    async def try_lock_for_evaluation(self, truck_id: str) -> bool:
        return await self._repo.try_lock_for_evaluation(truck_id)

    async def assign_route(self, truck_id: str, route) -> None:
        raise NotImplementedError

    async def complete_route(self, truck_id: str) -> None:
        raise NotImplementedError

    async def interrupt_route(self, truck_id: str, reason: str) -> None:
        raise NotImplementedError

    async def schedule_maintenance(self, truck_id: str) -> None:
        raise NotImplementedError
