"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "factories",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("capacity_total", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "stores",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "factory_products",
        sa.Column("factory_id", sa.String(50), nullable=False),
        sa.Column("material_id", sa.String(50), nullable=False),
        sa.Column("stock", sa.Float(), nullable=False),
        sa.Column("stock_reserved", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stock_max", sa.Float(), nullable=False),
        sa.Column("production_rate_max", sa.Float(), nullable=False),
        sa.Column("production_rate_current", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["factory_id"], ["factories.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("factory_id", "material_id"),
    )

    op.create_table(
        "factory_partner_warehouses",
        sa.Column("factory_id", sa.String(50), nullable=False),
        sa.Column("warehouse_id", sa.String(50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["factory_id"], ["factories.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("factory_id", "warehouse_id"),
    )

    op.create_table(
        "warehouse_stocks",
        sa.Column("warehouse_id", sa.String(50), nullable=False),
        sa.Column("material_id", sa.String(50), nullable=False),
        sa.Column("stock", sa.Float(), nullable=False),
        sa.Column("stock_reserved", sa.Float(), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("warehouse_id", "material_id"),
    )

    op.create_table(
        "store_stocks",
        sa.Column("store_id", sa.String(50), nullable=False),
        sa.Column("material_id", sa.String(50), nullable=False),
        sa.Column("stock", sa.Float(), nullable=False),
        sa.Column("demand_rate", sa.Float(), nullable=False),
        sa.Column("reorder_point", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("store_id", "material_id"),
    )

    op.create_table(
        "trucks",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("truck_type", sa.String(20), nullable=False),
        sa.Column("capacity_tons", sa.Float(), nullable=False),
        sa.Column("base_lat", sa.Float(), nullable=False),
        sa.Column("base_lng", sa.Float(), nullable=False),
        sa.Column("current_lat", sa.Float(), nullable=False),
        sa.Column("current_lng", sa.Float(), nullable=False),
        sa.Column("degradation", sa.Float(), nullable=False),
        sa.Column("breakdown_risk", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("factory_id", sa.String(50), nullable=True),
        sa.Column("cargo", postgresql.JSONB(), nullable=True),
        sa.Column("maintenance_start_tick", sa.Integer(), nullable=True),
        sa.Column("maintenance_duration_ticks", sa.Integer(), nullable=True),
        sa.Column("active_route_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["factory_id"], ["factories.id"]),
    )

    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("truck_id", sa.String(50), nullable=False),
        sa.Column("origin_type", sa.String(20), nullable=False),
        sa.Column("origin_id", sa.String(50), nullable=False),
        sa.Column("dest_type", sa.String(20), nullable=False),
        sa.Column("dest_id", sa.String(50), nullable=False),
        sa.Column("path", postgresql.JSONB(), nullable=False),
        sa.Column("timestamps", postgresql.JSONB(), nullable=False),
        sa.Column("eta_ticks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"]),
    )

    op.create_foreign_key(
        "fk_truck_active_route", "trucks", "routes", ["active_route_id"], ["id"]
    )

    op.create_table(
        "pending_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_type", sa.String(20), nullable=False),
        sa.Column("requester_id", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(50), nullable=False),
        sa.Column("material_id", sa.String(50), nullable=False),
        sa.Column("quantity_tons", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("age_ticks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_after_tick", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("eta_ticks", sa.Integer(), nullable=True),
        sa.Column("triggered_at_tick", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
    )

    op.create_foreign_key(
        "fk_route_order", "routes", "pending_orders", ["order_id"], ["id"]
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=True),
        sa.Column("entity_id", sa.String(50), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tick_start", sa.Integer(), nullable=False),
        sa.Column("tick_end", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "agent_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_constraint("fk_route_order", "routes", type_="foreignkey")
    op.drop_constraint("fk_truck_active_route", "trucks", type_="foreignkey")
    op.drop_table("agent_decisions")
    op.drop_table("events")
    op.drop_table("pending_orders")
    op.drop_table("routes")
    op.drop_table("trucks")
    op.drop_table("store_stocks")
    op.drop_table("warehouse_stocks")
    op.drop_table("factory_partner_warehouses")
    op.drop_table("factory_products")
    op.drop_table("stores")
    op.drop_table("warehouses")
    op.drop_table("factories")
    op.drop_table("materials")
