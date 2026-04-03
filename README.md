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

## ✨ Features

- 🤖 **Autonomous multi-agent system** — each entity runs a LangGraph `StateGraph` cycle (`perceive → decide → act`) powered by `gpt-4o-mini`, reacting to real supply chain events without human intervention
- 🗺️ **Real São Paulo road network** — trucks navigate actual OSM highways (Anhanguera, Bandeirantes, Dutra) via self-hosted Valhalla routing; animated live on a WebGL map with deck.gl `TripsLayer`
- ⚡ **Live simulation ticks** — deterministic physics engine advances the world every 10s (= 1 simulated hour); agent decisions fire-and-forget in the background and stream to the dashboard via WebSocket
- 🌪️ **Chaos injection** — inject disruptive events (truck strikes, road blocks, machine breakdowns, demand spikes) and watch agents autonomously adapt
- 🎮 **Game master dashboard** — fullscreen WebGL map with HUD overlays to inspect any entity, manage the world, and monitor the agent decision feed in real time
- 📦 **Self-hosted geo stack** — Martin tile server + Planetiler PMTiles + Valhalla routing, no paid map API required

## 🛠 Tech Stack

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
| Tile generation | Planetiler → PMTiles (one-time setup)                           |

## 🚀 Getting Started

### Prerequisites

- Docker 24+
- Python 3.11+
- Node 20+
- OpenAI API key

### Geo Data Setup (one-time, ~1 hour)

These large files are not versioned. Generate them once before starting the stack.

**1. Download OSM extract (~800 MB)**

```bash
wget https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf \
  -O geo/data/sudeste-latest.osm.pbf
```

**2. Generate vector tiles with Planetiler (~30 min, output ~2–4 GB)**

```bash
docker run -v $(pwd)/geo/data:/data ghcr.io/onthegomap/planetiler:latest \
  --osm-path=/data/sudeste-latest.osm.pbf \
  --output=/data/sudeste.pmtiles
```

**3. Build Valhalla routing graph (~20 min)**

```bash
mkdir -p geo/data/valhalla_tiles

docker run -v $(pwd)/geo/data:/custom_files \
  ghcr.io/gis-ops/docker-valhalla/valhalla:latest \
  valhalla_build_tiles -c /custom_files/valhalla.json \
  /custom_files/sudeste-latest.osm.pbf
```

### Installation

```bash
# Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY (required)

# Start all services
docker compose up
```

To start only infrastructure (postgres + redis):

```bash
docker compose up postgres redis
```

### Environment Variables

| Variable                | Description                                       | Required |
| ----------------------- | ------------------------------------------------- | -------- |
| `OPENAI_API_KEY`        | OpenAI API key for agent LLM calls                | ✅       |
| `OPENAI_MODEL`          | Model name (default: `gpt-4o-mini`)               | ⚪       |
| `DATABASE_URL`          | PostgreSQL connection string (asyncpg + PostGIS)  | ✅       |
| `REDIS_URL`             | Redis connection URL (Celery + Pub/Sub)           | ✅       |
| `API_HOST` / `API_PORT` | FastAPI server bind address                       | ⚪       |
| `VITE_API_URL`          | Backend REST base URL for the frontend            | ⚪       |
| `VITE_TILE_SERVER_URL`  | Martin tile server URL for MapLibre               | ⚪       |
| `TICK_INTERVAL_SECONDS` | Simulation tick interval in seconds (min 10)      | ⚪       |
| `MAX_AGENT_WORKERS`     | Max concurrent OpenAI calls (`asyncio.Semaphore`) | ⚪       |
| `VALHALLA_URL`          | Valhalla routing engine base URL                  | ⚪       |
| `OSM_DATA_PATH`         | Path to the `.osm.pbf` extract                    | ⚪       |
| `PMTILES_PATH`          | Path to the generated `.pmtiles` file             | ⚪       |

## 💻 Local Development

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

python -m uvicorn src.main:app --reload --port 8000
```

**Database**

```bash
cd backend

# Apply all migrations (create tables)
alembic upgrade head

# Seed the world with default data (3 factories, 3 warehouses, 5 stores, 6 trucks)
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.database.seed import seed_default_world
import os

async def run():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with AsyncSession(engine) as session:
        await seed_default_world(session)
        await session.commit()
    await engine.dispose()

asyncio.run(run())
"

# Roll back all migrations (drop all tables)
alembic downgrade base

# Generate a new migration after changing ORM models
alembic revision --autogenerate -m "describe_your_change"

# Check if models are in sync with the current migration head
alembic check

# Show current migration version applied to the database
alembic current

# Show full migration history
alembic history --verbose
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

## 🧪 Testing

```bash
cd backend
pytest
```

## 📦 Build

```bash
cd frontend
npm run build
```

## 📁 Project Structure

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

## 🌐 Service Ports

| Service              | Port |
| -------------------- | ---- |
| Backend (FastAPI)    | 8000 |
| Frontend (Vite)      | 5173 |
| PostgreSQL           | 5432 |
| Redis                | 6379 |
| Martin (tile server) | 3001 |
| Valhalla (routing)   | 8002 |

## 📄 License

MIT
