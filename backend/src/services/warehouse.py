import uuid

from src.services import ConflictError, NotFoundError


class WarehouseService:
    def __init__(self, repo, order_repo, publisher, factory_repo=None):
        self._repo = repo
        self._order_repo = order_repo
        self._publisher = publisher
        self._factory_repo = factory_repo

    async def list_warehouses(self):
        return await self._repo.get_all()

    async def get_warehouse(self, id: str):
        warehouse = await self._repo.get_by_id(id)
        if warehouse is None:
            raise NotFoundError(f"Warehouse '{id}' not found")
        return warehouse

    async def create_warehouse(self, data: dict):
        payload = data.copy()
        if "id" not in payload:
            payload["id"] = f"warehouse-{uuid.uuid4().hex[:8]}"
        if "status" not in payload:
            payload["status"] = "operating"
        return await self._repo.create(payload)

    async def update_warehouse(self, id: str, data: dict):
        warehouse = await self._repo.get_by_id(id)
        if warehouse is None:
            raise NotFoundError(f"Warehouse '{id}' not found")
        return await self._repo.update(id, data)

    async def delete_warehouse(self, id: str) -> None:
        warehouse = await self._repo.get_by_id(id)
        if warehouse is None:
            raise NotFoundError(f"Warehouse '{id}' not found")
        cancelled_as_requester = await self._order_repo.bulk_cancel_by_requester(
            id, "requester_deleted"
        )
        await self._release_upstream_reservations(cancelled_as_requester)
        await self._order_repo.bulk_cancel_by_target(id, "target_deleted")
        await self._repo.delete(id)
        await self._publisher.publish_event(
            "entity_removed", {"entity_type": "warehouse", "entity_id": id}
        )

    async def _release_upstream_reservations(self, cancelled_orders) -> None:
        if not cancelled_orders:
            return
        for info in cancelled_orders:
            if not getattr(info, "was_confirmed", False):
                continue
            if info.target_type == "factory" and self._factory_repo is not None:
                await self._factory_repo.release_reserved(
                    info.target_id, info.material_id, info.quantity_tons
                )
            elif info.target_type == "warehouse":
                await self._repo.release_reserved(
                    info.target_id, info.material_id, info.quantity_tons
                )

    async def confirm_order(self, order_id, eta_ticks: int):
        order = await self._order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order '{order_id}' not found")
        success = await self._repo.atomic_reserve_stock(
            order.target_id, order.material_id, order.quantity_tons
        )
        if not success:
            raise ConflictError(
                f"Insufficient stock to reserve {order.quantity_tons} tons "
                f"of material '{order.material_id}' in warehouse '{order.target_id}'"
            )
        return await self._order_repo.update_status(
            order_id, status="confirmed", eta_ticks=eta_ticks
        )

    async def reject_order(self, order_id, reason: str, retry_after_ticks: int | None = None):
        order = await self._order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order '{order_id}' not found")
        if order.status == "confirmed":
            await self._repo.release_reserved(
                order.target_id, order.material_id, order.quantity_tons
            )
        kwargs = {"rejection_reason": reason}
        if retry_after_ticks is not None:
            kwargs["retry_after_tick"] = (order.age_ticks or 0) + retry_after_ticks
        return await self._order_repo.update_status(
            order_id, status="rejected", **kwargs
        )

    async def adjust_stock(self, id: str, material_id: str, delta: float) -> None:
        warehouse = await self._repo.get_by_id(id)
        if warehouse is None:
            raise NotFoundError(f"Warehouse '{id}' not found")
        stock_entry = await self._repo.get_stock(id, material_id)
        if stock_entry is None:
            raise NotFoundError(f"Stock entry not found for warehouse '{id}' and material '{material_id}'")
        new_stock = stock_entry.stock + delta
        if new_stock < 0:
            raise ValueError(f"stock cannot be negative: {new_stock}")
        total_stock = sum(
            s.stock for s in (await self._repo.get_all_stocks(id))
            if s.material_id != material_id
        ) + new_stock
        if total_stock > warehouse.capacity_total:
            raise ValueError(f"total stock {total_stock} exceeds warehouse capacity {warehouse.capacity_total}")
        await self._repo.update_stock(id, material_id, delta)
