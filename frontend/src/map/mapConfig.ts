import type { StyleSpecification } from "maplibre-gl";

const TILE_SERVER_URL =
  import.meta.env.VITE_TILE_SERVER_URL || "http://localhost:3001";

export const INITIAL_VIEW_STATE = {
  latitude: -22.9,
  longitude: -47.1,
  zoom: 7,
  pitch: 0,
  bearing: 0,
  minZoom: 5,
  maxZoom: 16,
};

export const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    openmaptiles: {
      type: "vector",
      url: `${TILE_SERVER_URL}/sudeste`,
    },
  },
  glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#0e0e1a" },
    },
    {
      id: "water",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "water",
      paint: { "fill-color": "#14213d" },
    },
    {
      id: "landcover",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "landcover",
      paint: { "fill-color": "#121226", "fill-opacity": 0.5 },
    },
    {
      id: "roads-highway",
      type: "line",
      source: "openmaptiles",
      "source-layer": "transportation",
      filter: ["==", "class", "motorway"],
      paint: { "line-color": "#2a2a4a", "line-width": 1.5 },
    },
    {
      id: "roads-major",
      type: "line",
      source: "openmaptiles",
      "source-layer": "transportation",
      filter: ["in", "class", "trunk", "primary"],
      paint: { "line-color": "#1f1f3a", "line-width": 1 },
    },
    {
      id: "roads-minor",
      type: "line",
      source: "openmaptiles",
      "source-layer": "transportation",
      filter: ["in", "class", "secondary", "tertiary"],
      paint: { "line-color": "#1a1a30", "line-width": 0.5 },
      minzoom: 9,
    },
    {
      id: "boundary-state",
      type: "line",
      source: "openmaptiles",
      "source-layer": "boundary",
      filter: ["==", "admin_level", 4],
      paint: {
        "line-color": "#3a3a5c",
        "line-width": 1,
        "line-dasharray": [3, 2],
      },
    },
    {
      id: "place-city",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      filter: ["==", "class", "city"],
      layout: {
        "text-field": ["get", "name"],
        "text-size": 12,
        "text-anchor": "center",
        "text-font": ["Open Sans Regular"],
      },
      paint: {
        "text-color": "#6a6a8e",
        "text-halo-color": "#0e0e1a",
        "text-halo-width": 1,
      },
      minzoom: 6,
    },
  ],
};

export const FACTORY_COLOR: [number, number, number] = [66, 133, 244];
export const WAREHOUSE_COLOR: [number, number, number] = [251, 188, 4];
export const STORE_COLOR: [number, number, number] = [52, 168, 83];
export const TRUCK_PROPRIETARIO_COLOR: [number, number, number] = [0, 188, 212];
export const TRUCK_TERCEIRO_COLOR: [number, number, number] = [255, 152, 0];
export const ALERT_COLOR: [number, number, number] = [234, 67, 53];

export const ROUTE_ACTIVE_COLOR: [number, number, number] = [76, 175, 80];
export const ROUTE_WARNING_COLOR: [number, number, number] = [255, 235, 59];
export const ROUTE_BLOCKED_COLOR: [number, number, number] = [244, 67, 54];
