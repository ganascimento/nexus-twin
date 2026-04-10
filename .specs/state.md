# Development State

> This file is maintained by the AI agent to track the current progress of feature development.
> It records which features are done, in progress, or pending — and captures important decisions made during implementation.
> It is NOT a place for project definitions (those live in design.md, prd.md, and CLAUDE.md).

---

## Feature Progress

| #   | Feature            | Status     | Notes                                                             |
| --- | ------------------ | ---------- | ----------------------------------------------------------------- |
| 01  | project_setup      | done       |                                                                   |
| 02  | db_models          | done       | enums.py adicionado retroativamente — Python Enum + String column |
| 03  | db_migrations_seed | done       |                                                                   |
| 04  | repositories       | done       |                                                                   |
| 05  | world_state        | done       |                                                                   |
| 06  | services_entities  | done        |                                                                   |
| 07  | simulation_engine  | done        |                                                                   |
| 08  | agent_base         | done        |                                                                  |
| 09  | agents             | done        |                                                                  |
| 10  | guardrails         | done        |                                                                   |
| 11  | agent_tools        | done        |                                                                   |
| 12  | services_chaos     | done        |                                                                  |
| 13  | api_rest           | done       |                                                                   |
| 14  | api_websocket      | done       |                                                                   |
| 15  | celery_workers     | done       |                                                                   |
| 16  | frontend_base      | pending    |                                                                   |
| 17  | frontend_map       | pending    |                                                                   |
| 18  | frontend_hud       | pending    |                                                                   |

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
- [06_services_entities] Novos métodos adicionados aos repositórios: `FactoryRepository.get_product`, `FactoryRepository.release_reserved`, `WarehouseRepository.get_stock`, `WarehouseRepository.atomic_reserve_stock`, `WarehouseRepository.release_reserved`, `StoreRepository.get_stock` — necessários para serviços de negócio, ausentes na feature 04.
- [07_simulation_engine] `EventRepository` estendido com `count_active_autonomous()` e `get_active_for_entity(entity_type, entity_id)` — necessários para avaliação de triggers e controle de caos autônomo.
- [07_simulation_engine] `agent_fn` em triggers é sempre `None` nesta feature — agentes reais chegam nas features 08–09; engine aceita qualquer callable.
- [09_agents] Métodos adicionados a repositórios existentes: `FactoryRepository.get_partner_warehouses(factory_id)`, `FactoryRepository.list_partner_for_warehouse(warehouse_id)`, `WarehouseRepository.list_by_region(region)`, `OrderRepository.get_pending_for_requester(requester_id)` — necessários para montagem do WorldStateSlice de cada agente.
- [12_services_chaos] `EventRepository.get_by_id(event_id)` adicionado — necessário para `ChaosService.resolve_event()` validar existência e status antes de resolver.
