import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def test_store_stock_decrements_by_demand_rate(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    response = await client.post("/simulation/tick")
    assert response.status_code == 200

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock = result.scalar_one()
    assert stock == pytest.approx(22.5 - 7.5)


async def test_factory_production_increments_stock(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await async_session.execute(
        text(
            "UPDATE factory_products SET production_rate_current=30 "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )
    await async_session.commit()

    response = await client.post("/simulation/tick")
    assert response.status_code == 200

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM factory_products WHERE factory_id='factory-003' AND material_id='cimento'")
    )
    stock = result.scalar_one()
    assert stock == pytest.approx(430.0)


async def test_factory_production_caps_at_stock_max(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await async_session.execute(
        text(
            "UPDATE factory_products SET stock=749, production_rate_current=5 "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )
    await async_session.commit()

    response = await client.post("/simulation/tick")
    assert response.status_code == 200

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM factory_products WHERE factory_id='factory-003' AND material_id='cimento'")
    )
    stock = result.scalar_one()
    assert stock == pytest.approx(750.0), (
        f"Stock was 749 + production_rate 5 but cap is 750, so delta must be 1; got {stock}"
    )


async def test_pending_orders_age_increments(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    order_id = str(uuid.uuid4())
    await async_session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, material_id, quantity_tons, status, age_ticks, created_at, updated_at) "
            "VALUES (:id, 'store', 'store-001', 'warehouse', 'warehouse-002', 'cimento', 10.0, 'pending', 0, now(), now())"
        ),
        {"id": order_id},
    )
    await async_session.commit()

    response = await client.post("/simulation/tick")
    assert response.status_code == 200

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT age_ticks FROM pending_orders WHERE id = :id"),
        {"id": order_id},
    )
    age = result.scalar_one()
    assert age == 1


async def test_factory_zero_production_rate_adds_nothing(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await async_session.execute(
        text(
            "UPDATE factory_products SET stock=200, production_rate_current=0 "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )
    await async_session.commit()

    await client.post("/simulation/tick")

    await async_session.rollback()
    stock = (await async_session.execute(
        text("SELECT stock FROM factory_products WHERE factory_id='factory-003' AND material_id='cimento'")
    )).scalar_one()
    assert stock == pytest.approx(200.0), (
        f"production_rate_current=0 must not change stock; got {stock}"
    )


async def test_factory_at_stock_max_zeros_production_rate(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await async_session.execute(
        text(
            "UPDATE factory_products SET stock=750, production_rate_current=30 "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )
    await async_session.commit()

    await client.post("/simulation/tick")

    await async_session.rollback()
    row = (await async_session.execute(
        text(
            "SELECT stock, production_rate_current FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )).one()
    assert float(row.stock) == pytest.approx(750.0), "Stock at max must not increase"
    assert float(row.production_rate_current) == pytest.approx(0.0), (
        "Production rate must be zeroed when stock == stock_max"
    )


async def test_order_age_increments_for_confirmed_and_rejected(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    pending_id = str(uuid.uuid4())
    confirmed_id = str(uuid.uuid4())
    rejected_id = str(uuid.uuid4())
    delivered_id = str(uuid.uuid4())

    for oid, status in [
        (pending_id, "pending"),
        (confirmed_id, "confirmed"),
        (rejected_id, "rejected"),
        (delivered_id, "delivered"),
    ]:
        await async_session.execute(
            text(
                "INSERT INTO pending_orders "
                "(id, requester_type, requester_id, target_type, target_id, "
                "material_id, quantity_tons, status, age_ticks, created_at, updated_at) "
                "VALUES (:id, 'store', 'store-001', 'warehouse', 'warehouse-002', "
                "'cimento', 10.0, :status, 5, now(), now())"
            ),
            {"id": oid, "status": status},
        )
    await async_session.commit()

    await client.post("/simulation/tick")
    await async_session.rollback()

    for oid, label, expected in [
        (pending_id, "pending", 6),
        (confirmed_id, "confirmed", 6),
        (rejected_id, "rejected", 6),
        (delivered_id, "delivered", 5),
    ]:
        age = (await async_session.execute(
            text("SELECT age_ticks FROM pending_orders WHERE id=:id"), {"id": oid}
        )).scalar_one()
        assert age == expected, f"Order in '{label}' status: expected age={expected}, got {age}"


async def test_world_state_published_to_redis(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    response = await client.post("/simulation/tick")
    assert response.status_code == 200

    published_channels = [call.args[0] for call in mock_redis.publish.call_args_list]
    assert "nexus:world_state" in published_channels
