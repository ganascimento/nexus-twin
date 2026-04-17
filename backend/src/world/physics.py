import math
import random


_ROAD_TORTUOSITY_FACTOR = 1.3


def calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    straight_line_km = earth_radius_km * 2 * math.asin(math.sqrt(a))
    return straight_line_km * _ROAD_TORTUOSITY_FACTOR


def calculate_eta_ticks(distance_km: float, avg_speed_kmh: float = 60.0) -> int:
    return max(1, math.ceil(distance_km / avg_speed_kmh))


def calculate_degradation_delta(distance_km: float, cargo_tons: float, capacity_tons: float) -> float:
    if distance_km == 0 or capacity_tons == 0 or cargo_tons == 0:
        return 0.0
    return (distance_km / 1000) * (0.01 + 0.04 * (cargo_tons / capacity_tons))


_BREAKDOWN_RISK_THRESHOLD = 0.70
_BREAKDOWN_RISK_BASE_AT_THRESHOLD = 0.07
_BREAKDOWN_RISK_EXPONENTIAL_COEFF = (_BREAKDOWN_RISK_BASE_AT_THRESHOLD - 1.0) / -(1.0 - _BREAKDOWN_RISK_THRESHOLD) ** 2


def calculate_breakdown_risk(degradation: float) -> float:
    if degradation <= _BREAKDOWN_RISK_THRESHOLD:
        result = degradation * 0.1
    else:
        result = _BREAKDOWN_RISK_BASE_AT_THRESHOLD + (degradation - _BREAKDOWN_RISK_THRESHOLD) ** 2 * _BREAKDOWN_RISK_EXPONENTIAL_COEFF
    return min(1.0, max(0.0, result))


def is_trip_blocked(degradation: float) -> bool:
    return degradation >= 0.95


def roll_breakdown(breakdown_risk: float) -> bool:
    if breakdown_risk <= 0:
        return False
    return random.random() < breakdown_risk


def calculate_maintenance_ticks(degradation: float) -> int:
    return round(2 + degradation * 22)


def evaluate_replenishment_trigger(
    stock: float,
    min_stock: float,
    demand_rate: float,
    lead_time_ticks: int,
    safety_factor: float = 1.5,
) -> bool:
    if demand_rate <= 0:
        return False
    return (stock - min_stock) / demand_rate < lead_time_ticks * safety_factor
