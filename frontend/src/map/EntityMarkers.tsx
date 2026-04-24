import { useMemo } from "react";
import { Marker } from "react-map-gl/maplibre";
import { useWorldStore } from "../store/worldStore";
import { useInspect } from "../hooks/useInspect";
import { useSimulationClock } from "../hooks/useSimulationClock";
import { useMapZoom } from "../hooks/useMapZoom";
import type { ActiveRoute, TruckSnapshot, EntityType } from "../types/world";

const ZOOM_REFERENCE = 7;
const ZOOM_SCALE_COEFF = 0.25;
const ZOOM_SCALE_MIN = 0.6;
const ZOOM_SCALE_MAX = 2.0;

function computeZoomScale(zoom: number): number {
  const raw = 1 + (zoom - ZOOM_REFERENCE) * ZOOM_SCALE_COEFF;
  return Math.max(ZOOM_SCALE_MIN, Math.min(ZOOM_SCALE_MAX, raw));
}

type Heading = "east" | "west" | null;

function findSegment(
  timestamps: number[],
  currentTime: number,
): { index: number; progress: number } | null {
  if (timestamps.length < 2) return null;
  if (currentTime <= timestamps[0]) {
    return { index: 0, progress: 0 };
  }
  if (currentTime >= timestamps[timestamps.length - 1]) {
    return { index: timestamps.length - 2, progress: 1 };
  }
  for (let i = 0; i < timestamps.length - 1; i++) {
    const t0 = timestamps[i];
    const t1 = timestamps[i + 1];
    if (t0 <= currentTime && currentTime < t1) {
      const span = t1 - t0;
      const progress = span > 0 ? (currentTime - t0) / span : 0;
      return { index: i, progress };
    }
  }
  return { index: timestamps.length - 2, progress: 1 };
}

function getTruckPlacement(
  truck: TruckSnapshot,
  route: ActiveRoute | undefined,
  currentTime: number,
): { lng: number; lat: number; heading: Heading } {
  if (
    !route
    || route.path.length < 2
    || route.timestamps.length < 2
    || route.path.length !== route.timestamps.length
  ) {
    return { lng: truck.current_lng, lat: truck.current_lat, heading: null };
  }

  const seg = findSegment(route.timestamps, currentTime);
  if (seg === null) {
    return { lng: truck.current_lng, lat: truck.current_lat, heading: null };
  }

  const [lng0, lat0] = route.path[seg.index];
  const [lng1, lat1] = route.path[seg.index + 1];
  const lng = lng0 + seg.progress * (lng1 - lng0);
  const lat = lat0 + seg.progress * (lat1 - lat0);

  const [startLng] = route.path[0];
  const [endLng] = route.path[route.path.length - 1];
  const tripDx = endLng - startLng;
  const heading: Heading = tripDx < 0 ? "west" : "east";

  return { lng, lat, heading };
}

interface EntityMarkerProps {
  lng: number;
  lat: number;
  icon: string;
  size?: number;
  flipped?: boolean;
  alertRing?: string | null;
  badge?: string | null;
  onClick: () => void;
}

function EntityMarker({
  lng,
  lat,
  icon,
  size = 26,
  flipped = false,
  alertRing = null,
  badge = null,
  onClick,
}: EntityMarkerProps) {
  return (
    <Marker longitude={lng} latitude={lat} anchor="center">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        className="relative flex items-center justify-center cursor-pointer bg-transparent border-0 p-0 select-none"
        style={{
          width: size + 8,
          height: size + 8,
          filter: alertRing
            ? `drop-shadow(0 0 4px ${alertRing}) drop-shadow(0 0 8px ${alertRing})`
            : "drop-shadow(0 1px 2px rgba(0,0,0,0.6))",
        }}
      >
        <span
          aria-hidden="true"
          className="leading-none pointer-events-none"
          style={{
            fontSize: size,
            transform: flipped ? "scaleX(-1)" : undefined,
            display: "inline-block",
          }}
        >
          {icon}
        </span>
        {badge && (
          <span
            className="absolute -top-1 -right-1 text-xs pointer-events-none"
            aria-hidden="true"
          >
            {badge}
          </span>
        )}
      </button>
    </Marker>
  );
}

const FACTORY_ALERT_COLOR = "rgba(239, 68, 68, 0.9)";
const WAREHOUSE_ALERT_COLOR = "rgba(245, 158, 11, 0.9)";
const STORE_ALERT_COLOR = "rgba(239, 68, 68, 0.9)";
const TRUCK_BROKEN_COLOR = "rgba(239, 68, 68, 0.95)";
const TRUCK_MAINTENANCE_COLOR = "rgba(249, 115, 22, 0.9)";

export default function EntityMarkers() {
  const factories = useWorldStore((s) => s.factories);
  const warehouses = useWorldStore((s) => s.warehouses);
  const stores = useWorldStore((s) => s.stores);
  const trucks = useWorldStore((s) => s.trucks);
  const activeRoutes = useWorldStore((s) => s.activeRoutes);
  const trucksVisible = useWorldStore((s) => s.trucksVisible);
  const selectEntity = useInspect((s) => s.selectEntity);
  const currentTime = useSimulationClock();
  const zoom = useMapZoom();
  const scale = computeZoomScale(zoom);

  const routeByTruck = useMemo(() => {
    const m = new Map<string, ActiveRoute>();
    for (const r of activeRoutes) {
      if (r.status !== "active") continue;
      m.set(r.truck_id, r);
    }
    return m;
  }, [activeRoutes]);

  const handleSelect = (id: string, type: EntityType) => selectEntity(id, type);

  return (
    <>
      {factories.map((f) => (
        <EntityMarker
          key={`f-${f.id}`}
          lng={f.lng}
          lat={f.lat}
          icon="🏭"
          size={Math.round(28 * scale)}
          alertRing={f.status !== "operating" ? FACTORY_ALERT_COLOR : null}
          onClick={() => handleSelect(f.id, "factory")}
        />
      ))}

      {warehouses.map((w) => (
        <EntityMarker
          key={`w-${w.id}`}
          lng={w.lng}
          lat={w.lat}
          icon="📦"
          size={Math.round(26 * scale)}
          alertRing={w.status !== "operating" ? WAREHOUSE_ALERT_COLOR : null}
          onClick={() => handleSelect(w.id, "warehouse")}
        />
      ))}

      {stores.map((s) => (
        <EntityMarker
          key={`s-${s.id}`}
          lng={s.lng}
          lat={s.lat}
          icon="🏪"
          size={Math.round(24 * scale)}
          alertRing={s.status !== "open" ? STORE_ALERT_COLOR : null}
          onClick={() => handleSelect(s.id, "store")}
        />
      ))}

      {trucksVisible && trucks.map((t) => {
        const route = routeByTruck.get(t.id);
        const { lng, lat, heading } = getTruckPlacement(t, route, currentTime);
        const alertRing =
          t.status === "broken"
            ? TRUCK_BROKEN_COLOR
            : t.status === "maintenance"
              ? TRUCK_MAINTENANCE_COLOR
              : null;
        const badge =
          t.status === "broken"
            ? "🛠️"
            : t.status === "maintenance"
              ? "🔧"
              : null;
        return (
          <EntityMarker
            key={`t-${t.id}`}
            lng={lng}
            lat={lat}
            icon="🚚"
            size={Math.round(24 * scale)}
            flipped={heading === "west"}
            alertRing={alertRing}
            badge={badge}
            onClick={() => handleSelect(t.id, "truck")}
          />
        );
      })}
    </>
  );
}
