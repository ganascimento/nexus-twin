from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel


class SalesHistoryResult(BaseModel):
    entity_id: str
    material_id: str
    total_sold: float
    average_per_tick: float
    trend: Literal["increasing", "stable", "decreasing"]


TRENDS = ["increasing", "stable", "decreasing"]


@tool
def sales_history(entity_id: str, material_id: str, last_n_ticks: int) -> SalesHistoryResult:
    """Retrieve sales history for a specific entity and material over a number of ticks."""
    seed = abs(hash((entity_id, material_id)))
    total_sold = round((seed % 1000) + 50, 2)
    trend = TRENDS[seed % 3]
    safe_ticks = max(last_n_ticks, 1)
    average_per_tick = round(total_sold / safe_ticks, 2)

    return SalesHistoryResult(
        entity_id=entity_id,
        material_id=material_id,
        total_sold=total_sold,
        average_per_tick=average_per_tick,
        trend=trend,
    )
