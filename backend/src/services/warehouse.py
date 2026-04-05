from src.services import NotFoundError


class WarehouseService:
    def __init__(self, repo, order_repo, publisher):
        self._repo = repo
        self._order_repo = order_repo
        self._publisher = publisher

    async def list_warehouses(self):
        return await self._repo.get_all()

    async def get_warehouse(self, id: str):
        warehouse = await self._repo.get_by_id(id)
        if warehouse is None:
            raise NotFoundError(id)
        return warehouse

    async def create_warehouse(self, data: dict):
        return await self._repo.create(data)

    async def update_warehouse(self, id: str, data: dict):
        warehouse = await self._repo.get_by_id(id)
        if warehouse is None:
            raise NotFoundError(id)
        return await self._repo.update(id, data)

    async def delete_warehouse(self, id: str) -> None:
        await self._order_repo.bulk_cancel_by_target(id, "target_deleted")
        await self._repo.delete(id)
        await self._publisher.publish_event(
            "entity_removed", {"entity_type": "warehouse", "entity_id": id}
        )

    async def confirm_order(self, order_id, eta_ticks: int):
        order = await self._order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(order_id)
        success = await self._repo.atomic_reserve_stock(
            order.target_id, order.material_id, order.quantity_tons
        )
        if not success:
            return None
        return await self._order_repo.update_status(
            order_id, status="confirmed", eta_ticks=eta_ticks
        )

    async def reject_order(self, order_id, reason: str):
        return await self._order_repo.update_status(
            order_id, status="rejected", rejection_reason=reason
        )

    async def adjust_stock(self, id: str, material_id: str, delta: float) -> None:
        stock_entry = await self._repo.get_stock(id, material_id)
        if stock_entry is None:
            raise NotFoundError(material_id)
        new_stock = stock_entry.stock + delta
        if new_stock < 0:
            raise ValueError(f"stock cannot be negative: {new_stock}")
        await self._repo.update_stock(id, material_id, delta)
