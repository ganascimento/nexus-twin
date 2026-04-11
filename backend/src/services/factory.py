from src.services import NotFoundError


class FactoryService:
    def __init__(self, repo, order_repo, publisher):
        self._repo = repo
        self._order_repo = order_repo
        self._publisher = publisher

    async def list_factories(self):
        return await self._repo.get_all()

    async def get_factory(self, id: str):
        factory = await self._repo.get_by_id(id)
        if factory is None:
            raise NotFoundError(f"Factory '{id}' not found")
        return factory

    async def create_factory(self, data: dict):
        return await self._repo.create(data)

    async def update_factory(self, id: str, data: dict):
        factory = await self._repo.get_by_id(id)
        if factory is None:
            raise NotFoundError(f"Factory '{id}' not found")
        return await self._repo.update(id, data)

    async def delete_factory(self, id: str) -> None:
        await self._order_repo.bulk_cancel_by_target(id, "target_deleted")
        await self._repo.delete(id)
        await self._publisher.publish_event(
            "entity_removed", {"entity_type": "factory", "entity_id": id}
        )

    async def adjust_stock(self, id: str, material_id: str, delta: float) -> None:
        product = await self._repo.get_product(id, material_id)
        if product is None:
            raise NotFoundError(f"Product not found for factory '{id}' and material '{material_id}'")
        new_stock = product.stock + delta
        if new_stock < 0:
            raise ValueError(f"stock cannot be negative: {new_stock}")
        if new_stock > product.stock_max:
            raise ValueError(f"stock exceeds stock_max: {new_stock} > {product.stock_max}")
        await self._repo.update_product_stock(id, material_id, delta)
