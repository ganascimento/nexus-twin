from celery import shared_task
from sqlalchemy import select, func

from src.database.models.agent_decision import AgentDecision
from src.database.models.order import PendingOrder
from src.database.models.store import StoreStock
from src.database.models.truck import Truck
from src.database.models.warehouse import WarehouseStock
from src.workers.celery_app import get_sync_session


@shared_task(name="generate_efficiency_report")
def generate_efficiency_report():
    with get_sync_session() as session:
        orders_delivered = session.execute(
            select(func.count()).select_from(PendingOrder).where(PendingOrder.status == "delivered")
        ).scalar()

        orders_late = session.execute(
            select(func.count()).select_from(PendingOrder).where(
                PendingOrder.status == "delivered",
                PendingOrder.age_ticks > PendingOrder.eta_ticks,
            )
        ).scalar()

        store_ruptures = session.execute(
            select(StoreStock.store_id, StoreStock.material_id).where(StoreStock.stock == 0)
        ).all()

        warehouse_ruptures = session.execute(
            select(WarehouseStock.warehouse_id, WarehouseStock.material_id).where(WarehouseStock.stock == 0)
        ).all()

        stock_ruptures = [
            {"entity_type": "store", "entity_id": row.store_id, "material_id": row.material_id}
            for row in store_ruptures
        ] + [
            {"entity_type": "warehouse", "entity_id": row.warehouse_id, "material_id": row.material_id}
            for row in warehouse_ruptures
        ]

        trucks = session.execute(select(Truck)).scalars().all()
        truck_utilization = {
            truck.id: {"status": truck.status} for truck in trucks
        }

        return {
            "orders_delivered": orders_delivered,
            "orders_late": orders_late,
            "stock_ruptures": stock_ruptures,
            "truck_utilization": truck_utilization,
        }


@shared_task(name="generate_decision_summary")
def generate_decision_summary(tick_start=None, tick_end=None):
    with get_sync_session() as session:
        if tick_start is None or tick_end is None:
            max_tick = session.execute(
                select(func.max(AgentDecision.tick))
            ).scalar()
            tick_end = max_tick
            tick_start = max_tick - 24

        rows = session.execute(
            select(
                AgentDecision.agent_type,
                AgentDecision.action,
                func.count().label("count"),
            )
            .where(AgentDecision.tick >= tick_start, AgentDecision.tick <= tick_end)
            .group_by(AgentDecision.agent_type, AgentDecision.action)
        ).all()

        result = {}
        for row in rows:
            if row.agent_type not in result:
                result[row.agent_type] = {}
            result[row.agent_type][row.action] = row.count

        return result
