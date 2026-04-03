# Development State

> This file is maintained by the AI agent to track the current progress of feature development.
> It records which features are done, in progress, or pending — and captures important decisions made during implementation.
> It is NOT a place for project definitions (those live in design.md, prd.md, and CLAUDE.md).

---

## Feature Progress

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 01 | project_setup | done | |
| 02 | db_models | done | enums.py adicionado retroativamente — Python Enum + String column |
| 03 | db_migrations_seed | done | |
| 04 | repositories | done | |
| 05 | world_state | pending | |
| 06 | services_entities | pending | |
| 07 | simulation_engine | pending | |
| 08 | agent_base | pending | |
| 09 | agents | pending | |
| 10 | guardrails | pending | |
| 11 | agent_tools | pending | |
| 12 | services_chaos | pending | |
| 13 | api_rest | pending | |
| 14 | api_websocket | pending | |
| 15 | celery_workers | pending | |
| 16 | frontend_base | pending | |
| 17 | frontend_map | pending | |
| 18 | frontend_hud | pending | |

---

## Status Legend

- `pending` — not started
- `tdd_phase1` — tests written, waiting for user approval before implementation
- `tdd_rejected` — user rejected the tests; Notes column describes what to revise
- `in_progress` — tests approved, implementation underway
- `done` — implemented and all tests passing
- `blocked` — blocked by a dependency or external decision

---

## Implementation Decisions

> Record decisions made during development that are not obvious from the code or specs.
> Format: `[feature] decision made — reason`

- [02_db_models] Python `enum.Enum` + `String` column para campos tipados
- [03_db_migrations_seed] `active_route_id` em `Truck` corrigido de `String(50)` para `UUID(as_uuid=True)` — FK para `routes.id` (UUID) exige tipos compatíveis no PostgreSQL
- [03_db_migrations_seed] `NullPool` no engine de testes — asyncpg connections são bound ao event loop; NullPool evita reuso de conexões entre function-scoped loops do pytest (`status`, `truck_type`, `agent_type`, etc.) — PostgreSQL native ENUM descartado por custo alto de migration em fase de evolução rápida do schema. Enums centralizados em `backend/src/enums.py`, importados por models, guardrails e agents. Guardrails Pydantic enforçam os valores na camada de aplicação. Campos extensíveis (`event_type`, `action`) permanecem string livre.

