import { PathLayer } from "@deck.gl/layers";
import type { ActiveRoute, EventPayload } from "../../types/world";
import {
  ROUTE_ACTIVE_COLOR,
  ROUTE_WARNING_COLOR,
  ROUTE_BLOCKED_COLOR,
} from "../mapConfig";

interface RouteDatum {
  id: string;
  path: [number, number][];
  color: [number, number, number];
}

function getRouteColor(
  route: ActiveRoute,
  blockedTruckIds: Set<string>,
  warningTruckIds: Set<string>,
): [number, number, number] {
  if (blockedTruckIds.has(route.truck_id)) return ROUTE_BLOCKED_COLOR;
  if (warningTruckIds.has(route.truck_id)) return ROUTE_WARNING_COLOR;
  return ROUTE_ACTIVE_COLOR;
}

export function createRoutesLayer(
  routes: ActiveRoute[],
  activeEvents: EventPayload[],
): PathLayer<RouteDatum> {
  const activeRoutes = routes.filter((r) => r.status === "active");

  const blockedTruckIds = new Set<string>();
  const warningTruckIds = new Set<string>();

  for (const event of activeEvents) {
    if (event.status !== "active" || !event.entity_id) continue;
    if (event.event_type === "route_blocked") {
      blockedTruckIds.add(event.entity_id);
    } else if (
      event.event_type === "storm" ||
      event.event_type === "traffic"
    ) {
      warningTruckIds.add(event.entity_id);
    }
  }

  const data: RouteDatum[] = activeRoutes.map((r) => ({
    id: r.id,
    path: r.path,
    color: getRouteColor(r, blockedTruckIds, warningTruckIds),
  }));

  return new PathLayer<RouteDatum>({
    id: "routes-layer",
    data,
    getPath: (d) => d.path,
    getColor: (d) => d.color,
    getWidth: 3,
    widthUnits: "pixels",
    opacity: 0.6,
    pickable: false,
    jointRounded: true,
    capRounded: true,
  });
}
