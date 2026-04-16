import uuid

from src.services import NotFoundError


class StoreService:
    def __init__(self, repo, order_service, publisher):
        self._repo = repo
        self._order_service = order_service
        self._publisher = publisher

    async def list_stores(self):
        return await self._repo.get_all()

    async def get_store(self, id: str):
        store = await self._repo.get_by_id(id)
        if store is None:
            raise NotFoundError(f"Store '{id}' not found")
        return store

    async def create_store(self, data: dict):
        payload = data.copy()
        if "id" not in payload:
            payload["id"] = f"store-{uuid.uuid4().hex[:8]}"
        if "status" not in payload:
            payload["status"] = "open"
        return await self._repo.create(payload)

    async def update_store(self, id: str, data: dict):
        store = await self._repo.get_by_id(id)
        if store is None:
            raise NotFoundError(f"Store '{id}' not found")
        return await self._repo.update(id, data)

    async def delete_store(self, id: str) -> None:
        store = await self._repo.get_by_id(id)
        if store is None:
            raise NotFoundError(f"Store '{id}' not found")
        await self._order_service.cancel_orders_from(requester_id=id, reason="requester_deleted")
        await self._order_service.cancel_orders_targeting(target_id=id, reason="target_deleted")
        await self._repo.delete(id)
        await self._publisher.publish_event("entity_removed", {"entity_type": "store", "entity_id": id})

    async def adjust_stock(self, id: str, material_id: str, delta: float) -> None:
        stock_entry = await self._repo.get_stock(id, material_id)
        if stock_entry is None:
            raise NotFoundError(f"Stock entry not found for store '{id}' and material '{material_id}'")
        new_stock = stock_entry.stock + delta
        if new_stock < 0:
            raise ValueError(f"stock cannot be negative: {new_stock}")
        await self._repo.update_stock(id, material_id, delta)

    async def create_order(self, data: dict):
        return await self._order_service.create_order(data)
