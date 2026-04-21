import { ScatterplotLayer } from "@deck.gl/layers";
import { TripsLayer } from "@deck.gl/geo-layers";
import type { Layer } from "@deck.gl/core";
import type { TruckSnapshot, ActiveRoute } from "../../types/world";
import { TRUCK_PROPRIETARIO_COLOR, TRUCK_TERCEIRO_COLOR } from "../mapConfig";

interface TripDatum {
  id: string;
  entityType: "truck";
  path: [number, number][];
  timestamps: number[];
  truckType: string;
  degradation: number;
}

interface AnimatedTruckDatum {
  id: string;
  entityType: "truck";
  position: [number, number];
  truckType: string;
  degradation: number;
  status: string;
}

interface StaticTruckDatum {
  id: string;
  entityType: "truck";
  position: [number, number];
  truckType: string;
  degradation: number;
  status: string;
}

function interpolatePosition(
  path: [number, number][],
  timestamps: number[],
  currentTime: number,
): [number, number] {
  if (path.length === 0) return [0, 0];
  if (path.length === 1 || timestamps.length < 2) return path[0];
  if (currentTime <= timestamps[0]) return path[0];
  if (currentTime >= timestamps[timestamps.length - 1]) {
    return path[path.length - 1];
  }
  for (let i = 0; i < timestamps.length - 1; i++) {
    const t0 = timestamps[i];
    const t1 = timestamps[i + 1];
    if (t0 <= currentTime && currentTime < t1) {
      const progress = (currentTime - t0) / (t1 - t0);
      const [lng0, lat0] = path[i];
      const [lng1, lat1] = path[i + 1];
      return [lng0 + progress * (lng1 - lng0), lat0 + progress * (lat1 - lat0)];
    }
  }
  return path[path.length - 1];
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
  const routeMap = new Map(routes.map((r) => [r.id, r]));

  const tripsData: TripDatum[] = [];
  const animatedData: AnimatedTruckDatum[] = [];
  const staticData: StaticTruckDatum[] = [];

  for (const truck of trucks) {
    if (truck.active_route_id) {
      const route = routeMap.get(truck.active_route_id);
      if (route && route.path.length > 0 && route.timestamps.length > 0) {
        tripsData.push({
          id: truck.id,
          entityType: "truck",
          path: route.path,
          timestamps: route.timestamps,
          truckType: truck.truck_type,
          degradation: truck.degradation,
        });
        animatedData.push({
          id: truck.id,
          entityType: "truck",
          position: interpolatePosition(
            route.path,
            route.timestamps,
            currentTime,
          ),
          truckType: truck.truck_type,
          degradation: truck.degradation,
          status: truck.status,
        });
        continue;
      }
    }

    staticData.push({
      id: truck.id,
      entityType: "truck",
      position: [truck.current_lng, truck.current_lat],
      truckType: truck.truck_type,
      degradation: truck.degradation,
      status: truck.status,
    });
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
        trailLength: 60000,
        widthMinPixels: 3,
        jointRounded: true,
        capRounded: true,
      }),
    );
  }

  if (animatedData.length > 0) {
    layers.push(
      new ScatterplotLayer<AnimatedTruckDatum>({
        id: "trucks-animated-layer",
        data: animatedData,
        getPosition: (d) => d.position,
        getRadius: 10,
        getFillColor: (d) =>
          d.truckType === "proprietario"
            ? TRUCK_PROPRIETARIO_COLOR
            : TRUCK_TERCEIRO_COLOR,
        getLineColor: [255, 255, 255],
        lineWidthMinPixels: 2,
        stroked: true,
        radiusUnits: "pixels",
        pickable: true,
        updateTriggers: {
          getPosition: [currentTime],
        },
      }),
    );
  }

  if (staticData.length > 0) {
    layers.push(
      new ScatterplotLayer<StaticTruckDatum>({
        id: "trucks-static-layer",
        data: staticData,
        getPosition: (d) => d.position,
        getRadius: 8,
        getFillColor: (d) =>
          d.truckType === "proprietario"
            ? TRUCK_PROPRIETARIO_COLOR
            : TRUCK_TERCEIRO_COLOR,
        getLineColor: [255, 255, 255],
        lineWidthMinPixels: 2,
        stroked: true,
        radiusUnits: "pixels",
        pickable: true,
      }),
    );
  }

  return layers;
}
