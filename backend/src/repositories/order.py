from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import PendingOrder
from src.database.models.route import Route

ACTIVE_STATUSES = ("pending", "confirmed")


@dataclass(frozen=True)
class CancelledOrderInfo:
    order_id: UUID
    requester_type: str
    requester_id: str
    target_type: str
    target_id: str
    material_id: str
    quantity_tons: float
    was_confirmed: bool


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, data: dict) -> PendingOrder:
        payload = data.copy()
        payload.setdefault("age_ticks", 0)
        order = PendingOrder(**payload)
        self._session.add(order)
        await self._session.flush()
        await self._session.refresh(order)
        return order

    async def get_by_id(self, id: UUID) -> PendingOrder | None:
        result = await self._session.execute(
            select(PendingOrder).where(PendingOrder.id == id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_requester_target_material(
        self, requester_id: str, target_id: str, material_id: str
    ) -> PendingOrder | None:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.requester_id == requester_id,
                PendingOrder.target_id == target_id,
                PendingOrder.material_id == material_id,
                PendingOrder.status.in_(ACTIVE_STATUSES),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def has_active_order(
        self, requester_id: str, material_id: str, target_id: str | None = None
    ) -> bool:
        stmt = select(PendingOrder.id).where(
            PendingOrder.requester_id == requester_id,
            PendingOrder.material_id == material_id,
            PendingOrder.status.in_(ACTIVE_STATUSES),
        )
        if target_id is not None:
            stmt = stmt.where(PendingOrder.target_id == target_id)
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_pending_for_target(self, target_id: str) -> list[PendingOrder]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.target_id == target_id,
                PendingOrder.status.in_(ACTIVE_STATUSES),
            )
        )
        return result.scalars().all()

    async def get_pending_for_requester(self, requester_id: str) -> list[PendingOrder]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.requester_id == requester_id,
                PendingOrder.status.in_(ACTIVE_STATUSES),
            )
        )
        return result.scalars().all()

    async def increment_all_age_ticks(self) -> None:
        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.status.in_(("pending", "confirmed", "rejected")))
            .values(age_ticks=PendingOrder.age_ticks + 1)
        )

    async def update_status(self, id: UUID, status: str, **kwargs) -> PendingOrder:
        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.id == id)
            .values(status=status, **kwargs)
        )
        result = await self._session.execute(
            select(PendingOrder).where(PendingOrder.id == id)
        )
        return result.scalar_one()

    async def get_untriggered_for_target(self, target_id: str) -> list[PendingOrder]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.target_id == target_id,
                PendingOrder.status == "pending",
                PendingOrder.triggered_at_tick.is_(None),
            )
        )
        return result.scalars().all()

    async def mark_triggered(self, order_id: UUID, tick: int) -> None:
        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.id == order_id)
            .values(triggered_at_tick=tick)
        )

    async def get_triggered_but_pending_for_target(self, target_id: str) -> list[PendingOrder]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.target_id == target_id,
                PendingOrder.status == "pending",
                PendingOrder.triggered_at_tick.isnot(None),
            )
        )
        return result.scalars().all()

    async def reset_triggered(self, order_id: UUID) -> None:
        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.id == order_id)
            .values(triggered_at_tick=None)
        )

    async def bulk_cancel_by_target(
        self, target_id: str, reason: str, skip_active_routes: bool = True
    ) -> list[CancelledOrderInfo]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.target_id == target_id,
                PendingOrder.status.in_(ACTIVE_STATUSES),
            )
        )
        orders = result.scalars().all()

        if skip_active_routes and orders:
            active_route_order_ids = (
                await self._session.execute(
                    select(Route.order_id).where(
                        Route.order_id.in_([o.id for o in orders]),
                        Route.status == "active",
                    )
                )
            ).scalars().all()
            active_set = set(active_route_order_ids)
            orders = [o for o in orders if o.id not in active_set]

        if not orders:
            return []

        ids = [o.id for o in orders]
        cancelled = [
            CancelledOrderInfo(
                order_id=o.id,
                requester_type=o.requester_type,
                requester_id=o.requester_id,
                target_type=o.target_type,
                target_id=o.target_id,
                material_id=o.material_id,
                quantity_tons=o.quantity_tons,
                was_confirmed=(o.status == "confirmed"),
            )
            for o in orders
        ]

        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.id.in_(ids))
            .values(status="cancelled", cancellation_reason=reason)
        )
        return cancelled

    async def bulk_cancel_by_requester(
        self, requester_id: str, reason: str
    ) -> list[CancelledOrderInfo]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.requester_id == requester_id,
                PendingOrder.status.in_(ACTIVE_STATUSES),
            )
        )
        orders = result.scalars().all()

        if not orders:
            return []

        ids = [o.id for o in orders]
        cancelled = [
            CancelledOrderInfo(
                order_id=o.id,
                requester_type=o.requester_type,
                requester_id=o.requester_id,
                target_type=o.target_type,
                target_id=o.target_id,
                material_id=o.material_id,
                quantity_tons=o.quantity_tons,
                was_confirmed=(o.status == "confirmed"),
            )
            for o in orders
        ]

        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.id.in_(ids))
            .values(status="cancelled", cancellation_reason=reason)
        )
        return cancelled

    async def get_retry_eligible(self, requester_id: str) -> list[PendingOrder]:
        result = await self._session.execute(
            select(PendingOrder).where(
                PendingOrder.requester_id == requester_id,
                PendingOrder.status == "rejected",
                PendingOrder.retry_after_tick.isnot(None),
                PendingOrder.age_ticks >= PendingOrder.retry_after_tick,
            )
        )
        return result.scalars().all()

    async def has_order_in_pipeline(self, requester_id: str, material_id: str) -> bool:
        result = await self._session.execute(
            select(PendingOrder.id).where(
                PendingOrder.requester_id == requester_id,
                PendingOrder.material_id == material_id,
                (
                    PendingOrder.status.in_(ACTIVE_STATUSES)
                    | (
                        (PendingOrder.status == "rejected")
                        & PendingOrder.retry_after_tick.isnot(None)
                        & (PendingOrder.age_ticks < PendingOrder.retry_after_tick)
                    )
                ),
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def clear_retry_after_tick(self, order_id: UUID) -> None:
        await self._session.execute(
            update(PendingOrder)
            .where(PendingOrder.id == order_id)
            .values(retry_after_tick=None)
        )

    async def get_confirmed_without_route(self, limit: int = 10) -> list[PendingOrder]:
        from sqlalchemy.orm import aliased
        route_alias = aliased(Route)
        stmt = (
            select(PendingOrder)
            .outerjoin(
                route_alias,
                (route_alias.order_id == PendingOrder.id) & (route_alias.status == "active"),
            )
            .where(
                PendingOrder.status == "confirmed",
                route_alias.id.is_(None),
            )
            .order_by(PendingOrder.age_ticks.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
