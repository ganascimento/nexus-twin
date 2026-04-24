import { useCallback, useMemo } from "react";
import { Map as MapGL } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useWorldStore } from "../store/worldStore";
import { useInspect } from "../hooks/useInspect";
import { useSimulationClock } from "../hooks/useSimulationClock";
import { INITIAL_VIEW_STATE, MAP_STYLE } from "./mapConfig";
import { createTrucksLayers } from "./layers/TrucksLayer";
import { createRoutesLayer } from "./layers/RoutesLayer";
import { createEventsLayer } from "./layers/EventsLayer";
import FloatingAnimations from "./FloatingAnimations";
import EntityMarkers from "./EntityMarkers";
import DeckGLOverlay from "./DeckGLOverlay";
import type { PickingInfo } from "@deck.gl/core";
import type { EntityType } from "../types/world";

interface PickedObject {
  id?: string;
  entityType?: EntityType;
  eventId?: string;
  eventType?: string;
}

export default function WorldMap() {
  const factories = useWorldStore((s) => s.factories);
  const warehouses = useWorldStore((s) => s.warehouses);
  const stores = useWorldStore((s) => s.stores);
  const trucks = useWorldStore((s) => s.trucks);
  const activeRoutes = useWorldStore((s) => s.activeRoutes);
  const activeEvents = useWorldStore((s) => s.activeEvents);

  const clearSelection = useInspect((s) => s.clearSelection);
  const selectEntity = useInspect((s) => s.selectEntity);

  const currentTime = useSimulationClock();

  const entityPositions = useMemo(() => {
    const positions = new Map<string, [number, number]>();
    for (const f of factories) positions.set(f.id, [f.lng, f.lat]);
    for (const w of warehouses) positions.set(w.id, [w.lng, w.lat]);
    for (const s of stores) positions.set(s.id, [s.lng, s.lat]);
    for (const t of trucks) positions.set(t.id, [t.current_lng, t.current_lat]);
    return positions;
  }, [factories, warehouses, stores, trucks]);

  const layers = useMemo(
    () => [
      ...createRoutesLayer(activeRoutes, activeEvents),
      ...createTrucksLayers(trucks, activeRoutes, currentTime),
      createEventsLayer(activeEvents, entityPositions),
    ],
    [trucks, activeRoutes, activeEvents, currentTime, entityPositions],
  );

  const handleDeckClick = useCallback(
    (info: PickingInfo) => {
      const obj = info.object as PickedObject | undefined;
      if (obj?.entityType && obj.id) {
        selectEntity(obj.id, obj.entityType);
      }
    },
    [selectEntity],
  );

  const handleMapClick = useCallback(() => {
    clearSelection();
  }, [clearSelection]);

  return (
    <MapGL
      initialViewState={INITIAL_VIEW_STATE}
      mapStyle={MAP_STYLE}
      onClick={handleMapClick}
      style={{ width: "100%", height: "100%" }}
    >
      <DeckGLOverlay layers={layers} onClick={handleDeckClick} interleaved />
      <EntityMarkers />
      <FloatingAnimations />
    </MapGL>
  );
}
