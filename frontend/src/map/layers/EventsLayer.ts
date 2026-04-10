import { ScatterplotLayer } from "@deck.gl/layers";
import type { EventPayload } from "../../types/world";

interface EventDatum {
  eventId: string;
  eventType: string;
  description: string;
  position: [number, number];
}

export function createEventsLayer(
  activeEvents: EventPayload[],
  entityPositions: Map<string, [number, number]>,
): ScatterplotLayer<EventDatum> {
  const data: EventDatum[] = [];

  for (const event of activeEvents) {
    if (event.status !== "active") continue;
    if (!event.entity_id) continue;

    const position = entityPositions.get(event.entity_id);
    if (!position) continue;

    data.push({
      eventId: event.event_id,
      eventType: event.event_type,
      description: event.description,
      position,
    });
  }

  return new ScatterplotLayer<EventDatum>({
    id: "events-layer",
    data,
    getPosition: (d) => d.position,
    getRadius: 800,
    getFillColor: [234, 67, 53, 160],
    getLineColor: [255, 255, 255],
    stroked: true,
    lineWidthMinPixels: 3,
    radiusUnits: "meters",
    pickable: true,
  });
}
