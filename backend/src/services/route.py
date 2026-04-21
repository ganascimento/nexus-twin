import os

import httpx
from loguru import logger

from src.repositories.route import RouteRepository
from src.world.physics import calculate_eta_ticks

VALHALLA_URL = os.getenv("VALHALLA_URL", "http://localhost:8002")

_VALHALLA_POLYLINE_PRECISION = 1e-6


def _decode_polyline6(encoded: str) -> list[list[float]]:
    coords: list[list[float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)
    while index < length:
        result = 0
        shift = 0
        while True:
            if index >= length:
                raise ValueError("Truncated polyline")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        result = 0
        shift = 0
        while True:
            if index >= length:
                raise ValueError("Truncated polyline")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng

        coords.append([lng * _VALHALLA_POLYLINE_PRECISION, lat * _VALHALLA_POLYLINE_PRECISION])
    return coords


class RouteService:
    def __init__(self, route_repo: RouteRepository):
        self._repo = route_repo

    async def compute_route(
        self,
        from_lat: float,
        from_lng: float,
        to_lat: float,
        to_lng: float,
        current_tick: int,
    ) -> dict:
        try:
            path, distance_km = await self._call_valhalla(from_lat, from_lng, to_lat, to_lng)
        except Exception as exc:
            logger.warning("Valhalla unavailable, using straight-line fallback: {}", exc)
            path = [[from_lng, from_lat], [to_lng, to_lat]]
            from src.world.physics import calculate_distance_km
            distance_km = calculate_distance_km(from_lat, from_lng, to_lat, to_lng)

        eta_ticks = calculate_eta_ticks(distance_km)
        timestamps = self._generate_timestamps(path, current_tick, eta_ticks)

        return {
            "path": path,
            "timestamps": timestamps,
            "distance_km": distance_km,
            "eta_ticks": eta_ticks,
        }

    async def create_route(
        self,
        truck_id: str,
        origin_type: str,
        origin_id: str,
        dest_type: str,
        dest_id: str,
        route_data: dict,
    ):
        from datetime import datetime, timezone

        create_data = {
            "truck_id": truck_id,
            "origin_type": origin_type,
            "origin_id": origin_id,
            "dest_type": dest_type,
            "dest_id": dest_id,
            "path": route_data["path"],
            "timestamps": route_data["timestamps"],
            "eta_ticks": route_data["eta_ticks"],
            "status": "active",
            "started_at": datetime.now(timezone.utc),
        }
        if "order_id" in route_data:
            create_data["order_id"] = route_data["order_id"]
        if "leg" in route_data:
            create_data["leg"] = route_data["leg"]
        return await self._repo.create(create_data)

    async def _call_valhalla(
        self, from_lat: float, from_lng: float, to_lat: float, to_lng: float
    ) -> tuple[list, float]:
        payload = {
            "locations": [
                {"lat": from_lat, "lon": from_lng},
                {"lat": to_lat, "lon": to_lng},
            ],
            "costing": "truck",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{VALHALLA_URL}/route", json=payload)
            resp.raise_for_status()
            data = resp.json()

        legs = data.get("trip", {}).get("legs", [])
        if not legs:
            raise ValueError("No route legs returned from Valhalla")

        shape = legs[0].get("shape", [])
        distance_km = data["trip"]["summary"]["length"]
        path = self._normalize_valhalla_shape(shape)
        if len(path) < 2:
            raise ValueError(f"Valhalla returned degenerate shape ({len(path)} points)")

        return path, distance_km

    @staticmethod
    def _normalize_valhalla_shape(shape) -> list[list[float]]:
        if isinstance(shape, str):
            return _decode_polyline6(shape)
        if not shape:
            return []
        first = shape[0]
        if isinstance(first, dict):
            return [[p["lon"], p["lat"]] for p in shape]
        if isinstance(first, (list, tuple)) and len(first) >= 2:
            return [[float(p[0]), float(p[1])] for p in shape]
        raise ValueError(f"Unrecognized Valhalla shape format: {type(first).__name__}")

    def _generate_timestamps(
        self, path: list, start_tick: int, eta_ticks: int
    ) -> list[int]:
        n = len(path)
        if n <= 1:
            return [start_tick]
        return [
            start_tick + round(i * eta_ticks / (n - 1)) for i in range(n)
        ]
