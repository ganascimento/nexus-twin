import { TripsLayer } from "@deck.gl/geo-layers";
import type { Layer } from "@deck.gl/core";
import type { TruckSnapshot, ActiveRoute } from "../../types/world";

interface TripDatum {
  id: string;
  entityType: "truck";
  path: [number, number][];
  timestamps: number[];
  truckType: string;
  degradation: number;
}

function getDegradationColor(degradation: number): [number, number, number] {
  if (degradation < 0.3) return [76, 175, 80];
  if (degradation < 0.6) return [255, 235, 59];
  if (degradation < 0.8) return [255, 152, 0];
  return [244, 67, 54];
}

export function createTrucksLayers(
  trucks: TruckSnapshot[],
  routes: ActiveRoute[],
  currentTime: number,
): Layer[] {
  const routeByTruck = new Map<string, ActiveRoute>();
  for (const r of routes) {
    if (r.status !== "active") continue;
    routeByTruck.set(r.truck_id, r);
  }

  const tripsData: TripDatum[] = [];

  for (const truck of trucks) {
    const route = routeByTruck.get(truck.id);
    if (route && route.path.length > 1 && route.timestamps.length > 1) {
      tripsData.push({
        id: truck.id,
        entityType: "truck",
        path: route.path,
        timestamps: route.timestamps,
        truckType: truck.truck_type,
        degradation: truck.degradation,
      });
    }
  }

  const layers: Layer[] = [];

  if (tripsData.length > 0) {
    layers.push(
      new TripsLayer<TripDatum>({
        id: "trucks-trips-layer",
        data: tripsData,
        getPath: (d) => d.path,
        getTimestamps: (d) => d.timestamps,
        getColor: (d) => getDegradationColor(d.degradation),
        currentTime,
        trailLength: 3000,
        widthMinPixels: 3,
        jointRounded: true,
        capRounded: true,
      }),
    );
  }

  return layers;
}
