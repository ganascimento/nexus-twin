<div align="center">

# Nexus Twin

A fully autonomous supply chain simulation where every entity — factory, warehouse, store, and truck — is an AI agent that perceives the world, makes decisions, and acts without human intervention.

![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat&logo=langchain&logoColor=white)
![React](https://img.shields.io/badge/React_18-61DAFB?style=flat&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostGIS-4169E1?style=flat&logo=postgresql&logoColor=white)

</div>

---

## Features

- **Autonomous multi-agent system** — each entity runs a LangGraph `StateGraph` cycle (`perceive > decide > act`) powered by `gpt-4o-mini`, reacting to supply chain events without human intervention
- **Real Sao Paulo road network** — trucks navigate actual OSM highways (Anhanguera, Bandeirantes, Dutra) via self-hosted Valhalla routing, animated live on a WebGL map with deck.gl `TripsLayer`
- **Live simulation ticks** — deterministic physics engine advances the world every 10s (= 1 simulated hour); agent decisions fire-and-forget in the background and stream to the dashboard via WebSocket
- **Chaos injection** — inject disruptive events (truck strikes, road blocks, machine breakdowns, demand spikes) and watch agents autonomously adapt
- **Game master dashboard** — fullscreen WebGL map with HUD overlays to inspect any entity, manage the world, and monitor the agent decision feed in real time
- **Self-hosted geo stack** — Martin tile server + Planetiler PMTiles + Valhalla routing, no paid map API required

## Tech Stack

| Layer           | Technology                                                      |
| --------------- | --------------------------------------------------------------- |
| Backend runtime | Python 3.11+, FastAPI, Uvicorn                                  |
| AI / Agents     | LangGraph `StateGraph`, OpenAI `gpt-4o-mini`                    |
| Agent tools     | LangChain `@tool` + `ToolNode`                                  |
| Guardrails      | Pydantic v2 (validates every agent decision before DB write)    |
| Database        | PostgreSQL 15+ with PostGIS                                     |
| Async jobs      | Celery + Redis (non-LLM background tasks)                       |
| Realtime        | FastAPI WebSockets + Redis Pub/Sub                              |
| Frontend        | React 18 + TypeScript + Vite                                    |
| Map / WebGL     | MapLibre GL JS 4 + deck.gl 9 (`TripsLayer`, `ScatterplotLayer`) |
| Global state    | Zustand (WorldState synced per tick via WebSocket)              |
| UI / HUD        | Tailwind CSS + shadcn/ui                                        |
| Tile server     | Martin (Rust) serving PMTiles                                   |
| Routing engine  | Valhalla (Docker) — truck-aware routing                         |
| Tile generation | Planetiler > PMTiles (one-time setup)                           |

## Getting Started

### Prerequisites

- **Docker 24+** and **Docker Compose** — for PostgreSQL, Redis, and the geo stack
- **Python 3.11+** — backend runtime
- **Node.js 20+** — frontend dev server
- **OpenAI API key** — with credit; agents use `gpt-4o-mini` (~$0.15/1M input tokens)

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd nexus-twin
```

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Frontend:**

```bash
cd frontend
npm install
```

### 2. Configure environment

The `.env` file lives inside `backend/`:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set your OpenAI API key:

```dotenv
OPENAI_API_KEY=sk-your-key-here
```

The other values default to `localhost` and work out of the box for local development.

### 3. Start infrastructure

All services (PostgreSQL, Redis, Martin tile server, Valhalla routing) are managed by Docker Compose. Backend and frontend run locally.

```bash
docker compose up -d
```

Wait for services to be healthy:

```bash
docker compose ps
```

> Martin and Valhalla require geo data to be generated first (see [Geo Data Setup](#geo-data-setup-one-time) below). Without it, the simulation still works but the map will be empty and routing unavailable.

### 4. Create and seed the database

From the `backend/` directory, with the venv activated:

```bash
cd backend

# Apply all migrations (creates tables + PostGIS extensions)
alembic upgrade head

# Seed the default world (3 materials, 3 factories, 3 warehouses, 5 stores, 6 trucks)
python scripts/seed.py
```

### 5. Run the application

Open two terminals:

**Terminal 1 — Backend:**

```bash
cd backend
source .venv/bin/activate
uvicorn src.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open your browser:

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost:5173      |
| API docs | http://localhost:8000/docs |

---

## Geo Data Setup (one-time)

The map and routing use real OpenStreetMap data from Sao Paulo state. These files are large and not versioned in git — you generate them once locally.

All files go into `geo/data/`. Run all commands from the project root.

### Step 1 — Download OSM extract (~800 MB)

```bash
wget https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf \
  -O geo/data/sudeste-latest.osm.pbf
```

### Step 2 — Generate vector tiles with Planetiler (~30 min, output ~2-4 GB)

These tiles are what the Martin tile server serves to MapLibre for rendering the base map.

Planetiler needs auxiliary datasets besides the OSM extract. Download them first to avoid connection issues during processing:

```bash
mkdir -p geo/data/sources

wget -O geo/data/sources/natural_earth_vector.sqlite.zip \
  https://naciscdn.org/naturalearth/packages/natural_earth_vector.sqlite.zip

wget -O geo/data/sources/water-polygons-split-3857.zip \
  https://osmdata.openstreetmap.de/download/water-polygons-split-3857.zip

wget -O geo/data/sources/lake_centerline.shp.zip \
  https://osmdata.openstreetmap.de/download/lake-centerline.shp.zip
```

Then run Planetiler (it will find the pre-downloaded files and skip to processing):

```bash
docker run --rm -v $(pwd)/geo/data:/data ghcr.io/onthegomap/planetiler:latest \
  --osm-path=/data/sudeste-latest.osm.pbf \
  --output=/data/sudeste.pmtiles
```

### Step 3 — Build Valhalla routing graph (~20-30 min)

Valhalla uses this graph to calculate real truck routes along OSM highways. Copy the PBF into the Valhalla directory and run the container — it detects the file and builds the routing graph automatically on startup.

```bash
mkdir -p geo/data/valhalla_tiles

cp geo/data/sudeste-latest.osm.pbf geo/data/valhalla_tiles/

docker run --rm -v $(pwd)/geo/data/valhalla_tiles:/custom_files \
  -e use_tiles_ignore_pbf=False \
  -e build_elevation=False \
  -e build_admins=False \
  ghcr.io/gis-ops/docker-valhalla/valhalla:latest

# After the build finishes, remove the copied PBF (only the generated tiles are needed)
rm geo/data/valhalla_tiles/sudeste-latest.osm.pbf
```

After all steps, your `geo/data/` directory should look like this:

```
geo/data/
├── sudeste-latest.osm.pbf    # ~800 MB — downloaded from Geofabrik
├── sudeste.pmtiles            # ~2-4 GB — generated by Planetiler
└── valhalla_tiles/            # ~1-2 GB — generated by Valhalla
```

Restart the infrastructure to pick up the new geo data:

```bash
docker compose restart martin valhalla
```

---

## Environment Variables

| Variable                | Description                                       | Required |
| ----------------------- | ------------------------------------------------- | -------- |
| `OPENAI_API_KEY`        | OpenAI API key for agent LLM calls                | Yes      |
| `OPENAI_MODEL`          | Model name (default: `gpt-4o-mini`)               | No       |
| `DATABASE_URL`          | PostgreSQL connection string (asyncpg + PostGIS)  | Yes      |
| `REDIS_URL`             | Redis connection URL (Celery + Pub/Sub)           | Yes      |
| `API_HOST` / `API_PORT` | FastAPI server bind address                       | No       |
| `VITE_API_URL`          | Backend REST base URL for the frontend            | No       |
| `VITE_TILE_SERVER_URL`  | Martin tile server URL for MapLibre               | No       |
| `TICK_INTERVAL_SECONDS` | Simulation tick interval in seconds (min 10)      | No       |
| `MAX_AGENT_WORKERS`     | Max concurrent OpenAI calls (`asyncio.Semaphore`) | No       |
| `VALHALLA_URL`          | Valhalla routing engine base URL                  | No       |

## Database Commands

All commands from `backend/` with the venv activated:

```bash
# Apply all migrations
alembic upgrade head

# Roll back all migrations
alembic downgrade base

# Generate a new migration after changing ORM models
alembic revision --autogenerate -m "describe_your_change"

# Check current migration version
alembic current

# Show full migration history
alembic history --verbose
```

## Testing

```bash
cd backend
pip install -e ".[test]"
pytest
```

Integration tests use `testcontainers` to spin up an ephemeral PostgreSQL — no external database needed.

## Build

```bash
cd frontend
npm run build
```

## Service Ports

| Service              | Port | Notes                |
| -------------------- | ---- | -------------------- |
| Frontend (Vite)      | 5173 | Dev server with HMR  |
| Backend (FastAPI)    | 8000 | REST API + WebSocket |
| PostgreSQL + PostGIS | 5432 | Docker container     |
| Redis                | 6379 | Docker container     |
| Martin (tile server) | 3001 | Requires geo data    |
| Valhalla (routing)   | 8002 | Requires geo data    |

## Project Structure

```
nexus-twin/
├── backend/
│   └── src/
│       ├── agents/          # LangGraph StateGraphs — one per entity type
│       ├── guardrails/      # Pydantic decision schemas — validated before every DB write
│       ├── simulation/      # Tick engine, physics, event publisher, chaos injection
│       ├── world/           # WorldState snapshot + domain entity models
│       ├── services/        # Business logic layer
│       ├── repositories/    # DB access layer (one file per aggregate)
│       ├── tools/           # LangChain @tool functions for agents
│       ├── workers/         # Celery tasks (non-LLM background jobs)
│       ├── api/             # FastAPI routes + WebSocket streaming
│       └── database/        # SQLAlchemy models, Alembic migrations, seed data
├── frontend/
│   └── src/
│       ├── map/             # deck.gl layers (trucks, nodes, routes, events)
│       ├── hud/             # Overlay UI (inspect panel, agent log, chaos controls)
│       ├── store/           # Zustand world state
│       └── hooks/           # WebSocket + inspect state hooks
├── geo/
│   └── data/               # Large files — not versioned (OSM, PMTiles, Valhalla tiles)
└── docker-compose.yml
```

## License

MIT
