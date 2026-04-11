import os

import httpx
from loguru import logger

from src.repositories.route import RouteRepository
from src.world.physics import calculate_eta_ticks

VALHALLA_URL = os.getenv("VALHALLA_URL", "http://localhost:8002")


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
        self, truck_id: str, origin_id: str, destination_id: str, route_data: dict
    ):
        return await self._repo.create({
            "truck_id": truck_id,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "path": route_data["path"],
            "timestamps": route_data["timestamps"],
            "distance_km": route_data["distance_km"],
            "eta_ticks": route_data["eta_ticks"],
            "status": "active",
        })

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
        path = [[p["lon"], p["lat"]] for p in shape] if isinstance(shape[0], dict) else shape

        return path, distance_km

    def _generate_timestamps(
        self, path: list, start_tick: int, eta_ticks: int
    ) -> list[int]:
        n = len(path)
        if n <= 1:
            return [start_tick]
        return [
            start_tick + round(i * eta_ticks / (n - 1)) for i in range(n)
        ]
