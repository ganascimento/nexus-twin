from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel


class WeatherResult(BaseModel):
    condition: str
    severity: Literal["none", "low", "medium", "high"]
    description: str


WEATHER_CONDITIONS = {
    0: ("clear", "none", "Clear skies with good visibility"),
    1: ("rain", "low", "Light rain with minor impact on travel"),
    2: ("storm", "medium", "Moderate storm with reduced visibility and wet roads"),
    3: ("severe_storm", "high", "Severe storm with flooding risk and dangerous driving conditions"),
}


@tool
def weather(lat: float, lng: float) -> WeatherResult:
    """Check current weather conditions at a geographic coordinate to assess travel safety."""
    severity_index = abs(hash((round(lat, 2), round(lng, 2)))) % 4
    condition, severity, description = WEATHER_CONDITIONS[severity_index]
    return WeatherResult(condition=condition, severity=severity, description=description)
