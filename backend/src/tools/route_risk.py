import math
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel


class RouteRiskResult(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    factors: list[str]
    estimated_delay_hours: float


RISK_FACTORS_BY_LEVEL = {
    "low": ["normal_traffic"],
    "medium": ["moderate_traffic", "construction_zone"],
    "high": ["heavy_traffic", "accident_history", "poor_road_condition"],
}


@tool
def route_risk(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
) -> RouteRiskResult:
    """Evaluate risk level for a route segment between two geographic points."""
    distance = math.sqrt((dest_lat - origin_lat) ** 2 + (dest_lng - origin_lng) ** 2)

    if distance < 1.0:
        risk_level = "low"
    elif distance < 3.0:
        risk_level = "medium"
    else:
        risk_level = "high"

    factors = RISK_FACTORS_BY_LEVEL[risk_level]
    estimated_delay_hours = round(distance * 0.5, 2)

    return RouteRiskResult(
        risk_level=risk_level,
        factors=factors,
        estimated_delay_hours=estimated_delay_hours,
    )
