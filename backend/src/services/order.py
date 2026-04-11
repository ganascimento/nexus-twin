from src.services import NotFoundError


class OrderService:
    def __init__(self, repo, warehouse_repo, factory_repo):
        self._repo = repo
        self._warehouse_repo = warehouse_repo
        self._factory_repo = factory_repo

    async def create_order(self, data: dict):
        payload = data.copy()
        payload["status"] = "pending"
        payload["age_ticks"] = 0
        return await self._repo.create(payload)

    async def increment_age_ticks(self, tick: int) -> None:
        await self._repo.increment_all_age_ticks()

    async def get_pending_orders_for(self, target_id: str):
        return await self._repo.get_pending_for_target(target_id)

    async def confirm_order(self, order_id, eta_ticks: int):
        return await self._repo.update_status(order_id, status="confirmed", eta_ticks=eta_ticks)

    async def reject_order(self, order_id, reason: str, retry_after: int):
        return await self._repo.update_status(
            order_id, status="rejected", rejection_reason=reason, retry_after_tick=retry_after
        )

    async def mark_delivered(self, order_id):
        order = await self._repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order '{order_id}' not found")
        if order.target_type == "warehouse":
            await self._warehouse_repo.release_reserved(
                order.target_id, order.material_id, order.quantity_tons
            )
        elif order.target_type == "factory":
            await self._factory_repo.release_reserved(
                order.target_id, order.material_id, order.quantity_tons
            )
        return await self._repo.update_status(order_id, status="delivered")

    async def cancel_orders_targeting(self, target_id: str, reason: str):
        return await self._repo.bulk_cancel_by_target(target_id, reason)

    async def cancel_orders_from(self, requester_id: str, reason: str):
        return await self._repo.bulk_cancel_by_requester(requester_id, reason)
