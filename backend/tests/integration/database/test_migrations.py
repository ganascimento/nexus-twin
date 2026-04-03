import threading

from alembic import command
from sqlalchemy import text

EXPECTED_TABLES = frozenset(
    {
        "materials",
        "factories",
        "factory_products",
        "factory_partner_warehouses",
        "warehouses",
        "warehouse_stocks",
        "stores",
        "store_stocks",
        "trucks",
        "routes",
        "pending_orders",
        "events",
        "agent_decisions",
    }
)


def _run_alembic(cfg, revision: str) -> None:
    exc_holder: list = []

    def _target():
        try:
            if revision == "head":
                command.upgrade(cfg, "head")
            else:
                command.downgrade(cfg, revision)
        except Exception as exc:
            exc_holder.append(exc)

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    if exc_holder:
        raise exc_holder[0]


async def _get_public_tables(session) -> set:
    result = await session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    return {row[0] for row in result.fetchall()}


async def _get_pk_columns(session, table_name: str) -> set:
    result = await session.execute(
        text(
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "WHERE tc.table_name = :table_name "
            "  AND tc.constraint_type = 'PRIMARY KEY' "
            "  AND tc.table_schema = 'public'"
        ),
        {"table_name": table_name},
    )
    return {row[0] for row in result.fetchall()}


async def test_all_tables_created(async_session):
    tables = await _get_public_tables(async_session)
    assert EXPECTED_TABLES.issubset(tables), (
        f"Missing tables: {EXPECTED_TABLES - tables}"
    )


async def test_factory_products_composite_pk(async_session):
    pk_cols = await _get_pk_columns(async_session, "factory_products")
    assert pk_cols == {"factory_id", "material_id"}


async def test_warehouse_stocks_composite_pk(async_session):
    pk_cols = await _get_pk_columns(async_session, "warehouse_stocks")
    assert pk_cols == {"warehouse_id", "material_id"}


async def test_store_stocks_composite_pk(async_session):
    pk_cols = await _get_pk_columns(async_session, "store_stocks")
    assert pk_cols == {"store_id", "material_id"}


async def test_downgrade_removes_all_tables(async_engine, alembic_cfg):
    _run_alembic(alembic_cfg, "base")

    async with async_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        tables = {row[0] for row in result.fetchall()}

    assert not EXPECTED_TABLES.intersection(tables), (
        f"Tables still present after downgrade: {EXPECTED_TABLES.intersection(tables)}"
    )

    _run_alembic(alembic_cfg, "head")
