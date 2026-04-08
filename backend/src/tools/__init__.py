from src.tools.weather import weather
from src.tools.route_risk import route_risk
from src.tools.sales_history import sales_history
from src.tools.stock_levels import warehouse_stock_levels, factory_stock_levels

FACTORY_TOOLS = [sales_history, warehouse_stock_levels]
WAREHOUSE_TOOLS = [sales_history, factory_stock_levels]
STORE_TOOLS = [sales_history, warehouse_stock_levels]
TRUCK_TOOLS = [weather, route_risk]
