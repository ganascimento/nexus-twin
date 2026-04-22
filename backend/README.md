<div align="center">

# 🐍 Nexus Twin — Backend

### Multi-agent simulation engine, physics tick loop, REST + WebSocket API.

<br />

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Pydantic](https://img.shields.io/badge/Pydantic_v2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Langfuse](https://img.shields.io/badge/Langfuse-0A0A0A?style=flat-square&logoColor=white)](https://langfuse.com/)
![Unit](https://img.shields.io/badge/unit_tests-637_passing-brightgreen?style=flat-square)
![Integration](https://img.shields.io/badge/integration_tests-202_passing-brightgreen?style=flat-square)

</div>

---

## 🧭 Overview

The backend is the brain of Nexus Twin. Every 10 seconds the **simulation engine** advances one tick: it runs the deterministic physics (truck positions, stock decay, age counters), evaluates **predictive triggers** for each entity, and fires the relevant LLM agents in the background. Agents are `StateGraph`s from LangGraph — one per entity type — that perceive a slice of the world, decide autonomously, pass the decision through a Pydantic guardrail, and persist. The decision's side effects (create order, dispatch truck, confirm pickup, etc.) are applied by the `DecisionEffectProcessor` in the same transaction.

> 👉 For product requirements and world lore, see **[`.specs/prd.md`](../.specs/prd.md)**
> 👉 For architecture + data model, see **[`.specs/design.md`](../.specs/design.md)**
> 👉 For the canonical architecture spec, see **[`../CLAUDE.md`](../CLAUDE.md)**

---

## 🏗️ Architecture at a glance

```
Tick N  (10s real = 1h simulated)
  │
  ├── engine.py reads WorldState from Postgres
  │
  ├── apply_physics()                     ← synchronous, no AI
  │       └── truck positions, stock decay, age_ticks, maintenance countdown
  │
  ├── evaluate_triggers()                 ← deterministic, no AI
  │       ├── Trucks    — pending events (route_blocked, arrived, breakdown)
  │       └── Store/Warehouse/Factory — (stock - reorder_point) / demand < lead_time × 1.5
  │
  ├── For each triggered agent:
  │       └── asyncio.create_task(agent.run_cycle(event))    ← fire-and-forget
  │
  ├── Publishes WorldState via Redis → WebSocket → Dashboard
  │
  └── Tick N+1 (engine does NOT wait for agents)

  ... (async background)
  └── Agent runs: perceive → [fast_path | LLM] → guardrail → persist → DecisionEffectProcessor
```

Each agent's graph:

```
perceive ──► fast_path ──► act  ← (if deterministic rule triggers)
                   │
                   └─► decide (LLM) ──► act
```

---

## 📁 Project structure

```
backend/src/
├── agents/               # LangGraph StateGraphs — one per entity
│   ├── base.py           # AgentState (TypedDict) + graph builder
│   ├── factory_agent.py
│   ├── warehouse_agent.py
│   ├── store_agent.py
│   ├── truck_agent.py
│   ├── master_agent.py   # supervisor graph — fires autonomous chaos
│   └── prompts/          # .md system prompts per agent (isolated from graph logic)
│
├── guardrails/           # Pydantic schemas — validate every agent decision
│   ├── store.py          # StoreDecision, OrderReplenishmentPayload
│   ├── warehouse.py      # WarehouseDecision, Confirm/Reject/RequestResupply
│   ├── factory.py        # FactoryDecision, StartProduction/SendStock/StopProduction
│   └── truck.py          # TruckDecision, Accept/Refuse/RequestMaintenance/Reroute
│
├── simulation/
│   ├── engine.py         # Tick loop, trigger evaluation, dispatch, publisher call
│   ├── events.py         # SimulationEvent dataclass + type constants
│   ├── publisher.py      # Redis pub/sub — world_state, decisions, events
│   └── chaos.py          # Autonomous chaos event injection (MasterAgent)
│
├── observability/
│   └── langfuse.py       # Callback handler (opt-in), metadata/session helpers
│
├── world/
│   ├── state.py          # WorldState snapshot (immutable, Pydantic)
│   ├── entities/         # Domain models — Material, Factory, Warehouse, Store, Truck
│   └── physics.py        # Deterministic formulas — distance, ETA, degradation
│
├── services/             # Business logic (one file per domain)
│   ├── simulation.py
│   ├── world_state.py
│   ├── material.py / factory.py / warehouse.py / store.py / truck.py
│   ├── chaos.py
│   ├── order.py
│   ├── route.py          # Valhalla integration + path normalization
│   ├── physics.py
│   ├── trigger_evaluation.py
│   └── decision_effect_processor.py    # Applies side effects of agent decisions
│
├── repositories/         # DB access (one per aggregate)
│   ├── material.py, factory.py, warehouse.py, store.py, truck.py
│   ├── route.py, order.py, event.py, agent_decision.py
│
├── database/
│   ├── session.py        # AsyncSession factory
│   ├── models/           # SQLAlchemy ORM models
│   ├── seed.py           # Default world seed
│   └── migrations/       # Alembic
│
├── api/
│   ├── routes/           # REST endpoints
│   ├── models/           # Pydantic request/response schemas
│   ├── websocket.py      # Redis subscriber → client forward
│   └── dependencies.py   # FastAPI Depends factories
│
├── enums/                # Shared enums (trucks, orders, events, facilities)
└── main.py               # FastAPI entry point
```

---

## 🚀 Running the backend standalone

From `nexus-twin/backend/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Apply migrations + seed the default world
alembic upgrade head
python scripts/seed.py

# Start the server
uvicorn src.main:app --reload --port 8000
```

Check **<http://localhost:8000/docs>** for the interactive OpenAPI UI.

---

## 🗄️ Database

### Migrations (Alembic)

All commands from `backend/` with the venv activated:

```bash
alembic upgrade head                              # apply all pending migrations
alembic downgrade base                            # roll everything back
alembic revision --autogenerate -m "change_xxx"   # create a new migration from model diffs
alembic current                                   # check current version
alembic history --verbose                         # see full history
```

### Seed

```bash
python scripts/seed.py
```

Seeds the default world from `src/database/seed.py`:

- **3 materials**: `tijolos`, `vergalhao`, `cimento`
- **3 factories**: Campinas (tijolos), Sorocaba (vergalhao), Votorantim (cimento)
- **3 warehouses**: Ribeirão Preto, Jundiaí, Mogi das Cruzes
- **5 stores**: SP capital + metropolitan region
- **6 trucks**: 2 factory-owned + 4 third-party (capacities 6, 10, 18, 22 tons)

---

## 🧪 Testing

```bash
pip install -e ".[test]"

pytest                              # 839 tests — everything
pytest tests/unit/                  # 637 unit tests — fast, mocked LLM
pytest tests/integration/           # 202 integration tests — ephemeral Postgres
pytest tests/unit/agents/           # just the agents layer
pytest -k "accept_contract"         # by keyword
pytest -x --tb=short                # stop on first failure, short traceback
```

### How it works

- **Unit tests** replace `ChatOpenAI` with `FakeListChatModel` from LangChain. `WorldState` is mocked. No network calls, no DB.
- **Integration tests** use `testcontainers` to spin up ephemeral PostgreSQL per session. LLM is mocked via an `autouse` fixture that swaps `ChatOpenAI` for a `_NoOpenAIStub` that raises if called — **guaranteed zero OpenAI calls during CI**.
- **Conventions**: tests mirror `src/` folder structure under `tests/unit/` and `tests/integration/`.

---

## 🔧 Configuration

All via env vars in `backend/.env` (template at `backend/.env.example`):

| Variable                | Purpose                                                | Required |
| ----------------------- | ------------------------------------------------------ | -------- |
| `OPENAI_API_KEY`        | OpenAI API key for agent LLM calls                     | Yes      |
| `OPENAI_MODEL`          | Model name — default `gpt-4o-mini`                     | No       |
| `OPENAI_MAX_RETRIES`    | Retries on OpenAI errors — default `0`                 | No       |
| `DATABASE_URL`          | PostgreSQL connection string (asyncpg + PostGIS)       | Yes      |
| `REDIS_URL`             | Redis connection URL (Celery + Pub/Sub)                | Yes      |
| `API_HOST` / `API_PORT` | FastAPI bind address                                   | No       |
| `TICK_INTERVAL_SECONDS` | Tick interval in seconds — min `10`                    | No       |
| `MAX_AGENT_WORKERS`     | Max concurrent OpenAI calls (`asyncio.Semaphore`)      | No       |
| `VALHALLA_URL`          | Valhalla routing engine base URL                       | No       |
| `LANGFUSE_PUBLIC_KEY`   | Langfuse public key (blank disables instrumentation)   | No       |
| `LANGFUSE_SECRET_KEY`   | Langfuse secret key (blank disables instrumentation)   | No       |
| `LANGFUSE_HOST`         | Langfuse host URL — default `http://localhost:3100`    | No       |

---

## 🧩 Conventions

- **All code in English** — variables, functions, classes, commits. No exceptions.
- **Expressive names over comments** — `calculate_replenishment_ticks()` instead of `calc()` + explanation.
- **No docstrings, no redundant comments** — the code explains itself through naming.
- **Typed enums** — shared in `src/enums/`, imported as `from src.enums import <Class>`. Column type stays `String` in the DB (Pydantic guardrails enforce values at the app layer).
- **TDD is mandatory** for every new feature (two phases: tests first, wait for approval, then implementation).

---

## 📚 Related docs

- **[`../README.md`](../README.md)** — project overview + quick start
- **[`../frontend/README.md`](../frontend/README.md)** — dashboard + map layers
- **[`../geo/README.md`](../geo/README.md)** — map data + routing graph setup
- **[`../.specs/prd.md`](../.specs/prd.md)** — product requirements (NPCs, chaos events, default world)
- **[`../.specs/design.md`](../.specs/design.md)** — database schema, endpoints, agent architecture
- **[`../CLAUDE.md`](../CLAUDE.md)** — canonical architecture spec
