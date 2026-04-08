from langchain_core.tools import tool
from pydantic import BaseModel


class WarehouseStockItem(BaseModel):
    material_id: str
    quantity: float
    capacity_remaining: float


class WarehouseStockResult(BaseModel):
    warehouse_id: str
    stocks: list[WarehouseStockItem]


class FactoryProductItem(BaseModel):
    material_id: str
    stock: float
    stock_max: float
    production_rate_current: float


class FactoryStockResult(BaseModel):
    factory_id: str
    products: list[FactoryProductItem]


SIMULATED_MATERIALS = ["mat_001", "mat_002", "mat_003"]


@tool
def warehouse_stock_levels(warehouse_id: str) -> WarehouseStockResult:
    """Query current stock levels and remaining capacity for a warehouse."""
    seed = abs(hash(warehouse_id))
    stocks = []
    for i, material_id in enumerate(SIMULATED_MATERIALS):
        item_seed = (seed + i * 7) % 1000
        capacity_total = 500.0
        quantity = round((item_seed % 400) + 20, 2)
        stocks.append(
            WarehouseStockItem(
                material_id=material_id,
                quantity=quantity,
                capacity_remaining=round(capacity_total - quantity, 2),
            )
        )

    return WarehouseStockResult(warehouse_id=warehouse_id, stocks=stocks)


@tool
def factory_stock_levels(factory_id: str) -> FactoryStockResult:
    """Query current production stock levels and rates for a factory."""
    seed = abs(hash(factory_id))
    products = []
    for i, material_id in enumerate(SIMULATED_MATERIALS):
        item_seed = (seed + i * 13) % 1000
        stock_max = 1000.0
        stock = round((item_seed % 800) + 50, 2)
        production_rate_current = round((item_seed % 50) + 5, 2)
        products.append(
            FactoryProductItem(
                material_id=material_id,
                stock=stock,
                stock_max=stock_max,
                production_rate_current=production_rate_current,
            )
        )

    return FactoryStockResult(factory_id=factory_id, products=products)
