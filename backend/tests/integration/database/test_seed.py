from sqlalchemy import text


async def test_materials_count(async_session, seeded_db):
    result = await async_session.execute(text("SELECT COUNT(*) FROM materials"))
    assert result.scalar() == 3


async def test_materials_ids(async_session, seeded_db):
    result = await async_session.execute(
        text("SELECT id, is_active FROM materials ORDER BY id")
    )
    rows = result.fetchall()
    ids = {row[0] for row in rows}
    assert ids == {"tijolos", "vergalhao", "cimento"}
    assert all(row[1] is True for row in rows)


async def test_factories_count(async_session, seeded_db):
    result = await async_session.execute(text("SELECT COUNT(*) FROM factories"))
    assert result.scalar() == 3


async def test_factory_001_values(async_session, seeded_db):
    result = await async_session.execute(
        text("SELECT name, lat, lng, status FROM factories WHERE id = 'factory-001'")
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "Tijolaria Anhanguera"
    assert abs(row[1] - (-22.9099)) < 0.0001
    assert abs(row[2] - (-47.0626)) < 0.0001
    assert row[3] == "operating"


async def test_factory_products_factory_001(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT stock, stock_max, production_rate_max, production_rate_current, stock_reserved "
            "FROM factory_products WHERE factory_id = 'factory-001' AND material_id = 'tijolos'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 12.0
    assert row[1] == 30.0
    assert row[2] == 2.0
    assert row[3] == 0.0
    assert row[4] == 0.0


async def test_factory_products_factory_002(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT stock, stock_max, production_rate_max "
            "FROM factory_products WHERE factory_id = 'factory-002' AND material_id = 'vergalhao'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 2000.0
    assert row[1] == 5000.0
    assert row[2] == 120.0


async def test_factory_products_factory_003(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT stock, stock_max, production_rate_max "
            "FROM factory_products WHERE factory_id = 'factory-003' AND material_id = 'cimento'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 400.0
    assert row[1] == 750.0
    assert row[2] == 30.0


async def test_partner_warehouses_count(async_session, seeded_db):
    result = await async_session.execute(
        text("SELECT COUNT(*) FROM factory_partner_warehouses")
    )
    assert result.scalar() == 7


async def test_partner_warehouses_priorities(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT warehouse_id, priority FROM factory_partner_warehouses "
            "WHERE factory_id = 'factory-001' ORDER BY priority"
        )
    )
    rows = result.fetchall()
    assert len(rows) == 2
    assert rows[0] == ("warehouse-002", 1)
    assert rows[1] == ("warehouse-003", 2)

    result = await async_session.execute(
        text(
            "SELECT warehouse_id, priority FROM factory_partner_warehouses "
            "WHERE factory_id = 'factory-003' ORDER BY priority"
        )
    )
    rows = result.fetchall()
    assert len(rows) == 3
    assert rows[0] == ("warehouse-001", 1)
    assert rows[1] == ("warehouse-002", 2)
    assert rows[2] == ("warehouse-003", 3)


async def test_warehouses_count(async_session, seeded_db):
    result = await async_session.execute(text("SELECT COUNT(*) FROM warehouses"))
    assert result.scalar() == 3


async def test_warehouse_stocks_values(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT stock, min_stock FROM warehouse_stocks "
            "WHERE warehouse_id = 'warehouse-001' AND material_id = 'vergalhao'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 500.0
    assert row[1] == 100.0

    result = await async_session.execute(
        text(
            "SELECT stock, min_stock FROM warehouse_stocks "
            "WHERE warehouse_id = 'warehouse-002' AND material_id = 'cimento'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 150.0
    assert row[1] == 25.0


async def test_stores_count(async_session, seeded_db):
    result = await async_session.execute(text("SELECT COUNT(*) FROM stores"))
    assert result.scalar() == 5


async def test_store_stocks_store_001(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT material_id, stock, demand_rate, reorder_point FROM store_stocks "
            "WHERE store_id = 'store-001' ORDER BY material_id"
        )
    )
    rows = {row[0]: (row[1], row[2], row[3]) for row in result.fetchall()}

    assert "tijolos" in rows
    assert rows["tijolos"] == (1.5, 0.5, 1.0)

    assert "vergalhao" in rows
    assert rows["vergalhao"] == (90.0, 30.0, 60.0)

    assert "cimento" in rows
    assert rows["cimento"] == (22.5, 7.5, 15.0)


async def test_trucks_count(async_session, seeded_db):
    result = await async_session.execute(text("SELECT COUNT(*) FROM trucks"))
    assert result.scalar() == 6


async def test_trucks_types(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT truck_type, COUNT(*) FROM trucks GROUP BY truck_type ORDER BY truck_type"
        )
    )
    rows = {row[0]: row[1] for row in result.fetchall()}
    assert rows.get("proprietario") == 2
    assert rows.get("terceiro") == 4


async def test_truck_001_values(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT capacity_tons, degradation, status, factory_id, current_lat "
            "FROM trucks WHERE id = 'truck-001'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 15.0
    assert row[1] == 0.20
    assert row[2] == "idle"
    assert row[3] == "factory-001"
    assert abs(row[4] - (-22.9099)) < 0.0001


async def test_truck_004_values(async_session, seeded_db):
    result = await async_session.execute(
        text(
            "SELECT capacity_tons, degradation, status, factory_id "
            "FROM trucks WHERE id = 'truck-004'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 18.0
    assert row[1] == 0.10
    assert row[2] == "idle"
    assert row[3] is None


async def test_seed_idempotent(async_session, seeded_db):
    from src.database.seed import seed_default_world

    await seed_default_world(async_session)

    for table, expected in [
        ("materials", 3),
        ("factories", 3),
        ("warehouses", 3),
        ("stores", 5),
        ("trucks", 6),
    ]:
        result = await async_session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        assert result.scalar() == expected, (
            f"Expected {expected} {table} after second seed call"
        )
