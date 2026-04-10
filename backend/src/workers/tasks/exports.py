from celery import shared_task
from sqlalchemy import select

from src.database.models.agent_decision import AgentDecision
from src.database.models.event import ChaosEvent
from src.database.models.factory import Factory, FactoryProduct
from src.database.models.store import Store, StoreStock
from src.database.models.truck import Truck
from src.database.models.warehouse import Warehouse, WarehouseStock
from src.workers.celery_app import get_sync_session


@shared_task(name="export_decision_history")
def export_decision_history(entity_id=None, limit=None):
    with get_sync_session() as session:
        query = select(AgentDecision).order_by(AgentDecision.tick.desc())

        if entity_id is not None:
            query = query.where(AgentDecision.entity_id == entity_id)

        if limit is not None:
            query = query.limit(limit)

        decisions = session.execute(query).scalars().all()

        return [
            {
                "tick": row.tick,
                "agent_type": row.agent_type,
                "entity_id": row.entity_id,
                "action": row.action,
                "reasoning_summary": row.reasoning,
                "created_at": row.created_at.isoformat(),
            }
            for row in decisions
        ]


@shared_task(name="export_event_history")
def export_event_history():
    with get_sync_session() as session:
        events = session.execute(select(ChaosEvent)).scalars().all()

        return [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "source": row.source,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "status": row.status,
                "tick_start": row.tick_start,
                "tick_end": row.tick_end,
                "created_at": row.created_at.isoformat(),
            }
            for row in events
        ]


@shared_task(name="export_world_snapshot")
def export_world_snapshot():
    with get_sync_session() as session:
        factories = session.execute(select(Factory)).scalars().all()
        products = session.execute(select(FactoryProduct)).scalars().all()
        warehouses = session.execute(select(Warehouse)).scalars().all()
        wh_stocks = session.execute(select(WarehouseStock)).scalars().all()
        stores = session.execute(select(Store)).scalars().all()
        s_stocks = session.execute(select(StoreStock)).scalars().all()
        trucks = session.execute(select(Truck)).scalars().all()

        products_by_factory = {}
        for p in products:
            products_by_factory.setdefault(p.factory_id, []).append({
                "material_id": p.material_id,
                "stock": p.stock,
                "stock_max": p.stock_max,
                "production_rate_current": p.production_rate_current,
            })

        wh_stocks_by_warehouse = {}
        for ws in wh_stocks:
            wh_stocks_by_warehouse.setdefault(ws.warehouse_id, []).append({
                "material_id": ws.material_id,
                "stock": ws.stock,
                "min_stock": ws.min_stock,
            })

        s_stocks_by_store = {}
        for ss in s_stocks:
            s_stocks_by_store.setdefault(ss.store_id, []).append({
                "material_id": ss.material_id,
                "stock": ss.stock,
                "demand_rate": ss.demand_rate,
                "reorder_point": ss.reorder_point,
            })

        return {
            "factories": [
                {
                    "id": f.id,
                    "name": f.name,
                    "lat": f.lat,
                    "lng": f.lng,
                    "status": f.status,
                    "products": products_by_factory.get(f.id, []),
                }
                for f in factories
            ],
            "warehouses": [
                {
                    "id": w.id,
                    "name": w.name,
                    "lat": w.lat,
                    "lng": w.lng,
                    "status": w.status,
                    "stocks": wh_stocks_by_warehouse.get(w.id, []),
                }
                for w in warehouses
            ],
            "stores": [
                {
                    "id": s.id,
                    "name": s.name,
                    "lat": s.lat,
                    "lng": s.lng,
                    "status": s.status,
                    "stocks": s_stocks_by_store.get(s.id, []),
                }
                for s in stores
            ],
            "trucks": [
                {
                    "id": t.id,
                    "truck_type": t.truck_type,
                    "status": t.status,
                    "current_lat": t.current_lat,
                    "current_lng": t.current_lng,
                    "cargo": t.cargo,
                    "degradation": t.degradation,
                }
                for t in trucks
            ],
        }
