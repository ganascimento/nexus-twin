<div align="center">

# 🎨 Nexus Twin — Frontend

### Fullscreen WebGL dashboard with real-time animated trucks over a São Paulo map.

<br />

[![React](https://img.shields.io/badge/React_18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![MapLibre](https://img.shields.io/badge/MapLibre_GL-396CB2?style=flat-square&logo=maplibre&logoColor=white)](https://maplibre.org/)
[![deck.gl](https://img.shields.io/badge/deck.gl_9-000000?style=flat-square&logo=mapbox&logoColor=white)](https://deck.gl/)
[![Zustand](https://img.shields.io/badge/Zustand-2D3748?style=flat-square&logoColor=white)](https://zustand-demo.pmnd.rs/)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)

</div>

---

## 🧭 Overview

The frontend is a **fullscreen WebGL dashboard** that renders the simulation as it unfolds. The map is a real base of São Paulo state served by the self-hosted **Martin** tile server. Over that, four **deck.gl** layers show the living world: nodes (factories, warehouses, stores) with status-aware colors, animated trucks following actual OSM highways, routes colored by status, and chaos-event icons. A **HUD** overlay lets the user inspect any entity, inject chaos events, and manage the world in real time.

The dashboard is **not** a Streamlit-style app — every frame is a GPU-accelerated WebGL render with smooth truck interpolation between ticks (`requestAnimationFrame` at 60 fps synced to wall-clock timestamps from the backend).

---

## 🏗️ Architecture

```
WebSocket (world_state / agent_decisions / events)
          │
          ▼
   ┌──────────────────┐
   │  worldStore      │  ← Zustand global state, synced per tick
   │  (WorldState)    │
   └──────────────────┘
          │
   ┌──────┴──────────────────────────────────────────────┐
   │                                                     │
   ▼                                                     ▼
WorldMap (fullscreen WebGL)                      HUD (overlay UI)
 ├── NodesLayer         factories/warehouses/stores
 ├── RoutesLayer        active truck routes
 ├── TrucksLayer        TripsLayer (trail) + Scatterplot (animated dot)
 └── EventsLayer        chaos event icons
                                                 ├── StatsBar
                                                 ├── AgentLog (decision feed)
                                                 ├── InspectPanel (click handler)
                                                 ├── ChaosPanel
                                                 └── WorldManagement
```

Truck animation uses wall-clock millisecond timestamps shipped by the backend: TripsLayer interpolates the trail while a ScatterplotLayer interpolates the **current position** per animation frame via `useAnimatedCurrentTime` — so the truck slides smoothly between ticks instead of teleporting every 10 seconds.

---

## 📁 Project structure

```
frontend/src/
├── map/
│   ├── WorldMap.tsx         # Fullscreen DeckGL canvas — composes all layers
│   ├── mapConfig.ts         # Initial viewport, MapLibre style URL, color constants
│   └── layers/
│       ├── NodesLayer.ts    # ScatterplotLayer — factories, warehouses, stores
│       ├── RoutesLayer.ts   # PathLayer — routes colored by status
│       ├── TrucksLayer.ts   # TripsLayer (trail) + ScatterplotLayer (animated truck)
│       └── EventsLayer.ts   # IconLayer — chaos events
│
├── hud/
│   ├── StatsBar.tsx         # Top bar — tick counter, alerts, connection status
│   ├── AgentLog.tsx         # Scrolling feed of agent decisions
│   ├── InspectPanel.tsx     # Side panel with entity details when clicked
│   ├── ChaosPanel.tsx       # Inject disruptive events
│   └── WorldManagement.tsx  # CRUD on materials, factories, warehouses, stores, trucks
│
├── store/
│   └── worldStore.ts        # Zustand — WorldState + decisions + connection status
│
├── hooks/
│   ├── useWorldSocket.ts    # WebSocket connection, auto-reconnect, pub/sub dispatch
│   ├── useAnimatedCurrentTime.ts   # requestAnimationFrame clock for truck animation
│   └── useInspect.ts        # Selection state (which entity is open in InspectPanel)
│
├── types/
│   └── world.ts             # Shared TS types — WorldStatePayload, ActiveRoute, etc
│
├── lib/
│   ├── api.ts               # REST client + normalizeWorldState
│   └── geo.ts               # Geo helpers — position interpolation, path utilities
│
└── App.tsx                  # Layout: <WorldMap /> fullscreen + HUD overlay
```

---

## 🚀 Running the frontend

From `nexus-twin/frontend/`:

```bash
npm install
npm run dev
```

Dashboard at **<http://localhost:5173>**.

> The frontend needs the backend running at `http://localhost:8000` (configurable via `VITE_API_URL`) and, ideally, geo data generated so the map is not blank. See the root **[`../README.md`](../README.md)** for the complete setup.

---

## 🛠️ Useful commands

```bash
npm run dev           # dev server with HMR
npm run build         # production build to dist/
npm run preview       # serve the built bundle locally
npx tsc --noEmit      # type-check without emitting files
```

---

## 🧩 Layers in detail

### `NodesLayer` — factories, warehouses, stores

`ScatterplotLayer` with radius proportional to stock level and color shifting to red when a facility is in critical state. Click opens the `InspectPanel`.

### `RoutesLayer` — active routes

`PathLayer` for every `ActiveRoute` in the world state. Color by status:

- 🟢 green — normal
- 🟡 yellow — traffic
- 🔴 red — blocked (chaos event)

### `TrucksLayer` — animated trucks

Two layers per truck in transit:

- **TripsLayer** — animated trail over the path, short `trailLength` so it feels like motion, color by `degradation` (green → yellow → orange → red).
- **ScatterplotLayer** — the truck itself as a dot, interpolated to the real position at `currentTime = Date.now()`. The hook `useAnimatedCurrentTime` drives re-renders at ~60 fps.

Trucks not in transit fall back to a static ScatterplotLayer at `current_lat/lng`.

### `EventsLayer` — chaos events

`IconLayer` that renders icons at the location of each active chaos event (strike, storm, machine breakdown, etc).

---

## 🔧 Configuration

Environment variables (Vite prefix `VITE_`):

| Variable                | Purpose                                  | Default                  |
| ----------------------- | ---------------------------------------- | ------------------------ |
| `VITE_API_URL`          | Backend REST + WebSocket base URL        | `http://localhost:8000`  |
| `VITE_TILE_SERVER_URL`  | Martin vector tile server                | `http://localhost:3001`  |

---

## 📚 Related docs

- **[`../README.md`](../README.md)** — project overview + quick start
- **[`../backend/README.md`](../backend/README.md)** — simulation engine + agents
- **[`../geo/README.md`](../geo/README.md)** — map data + routing graph setup
