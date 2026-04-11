# Development State

> This file is maintained by the AI agent to track the current progress of feature development.
> It records which features are done, in progress, or pending — and captures important decisions made during implementation.
> It is NOT a place for project definitions (those live in design.md, prd.md, and CLAUDE.md).

---

## Feature Progress

| #   | Feature              | Status | Notes                                                                  |
| --- | -------------------- | ------ | ---------------------------------------------------------------------- |
| 01  | project_setup        | done   |                                                                        |
| 02  | db_models            | done   | enums.py adicionado retroativamente — Python Enum + String column      |
| 03  | db_migrations_seed   | done   |                                                                        |
| 04  | repositories         | done   |                                                                        |
| 05  | world_state          | done   |                                                                        |
| 06  | services_entities    | done   |                                                                        |
| 07  | simulation_engine    | done   |                                                                        |
| 08  | agent_base           | done   |                                                                        |
| 09  | agents               | done   |                                                                        |
| 10  | guardrails           | done   |                                                                        |
| 11  | agent_tools          | done   |                                                                        |
| 12  | services_chaos       | done   |                                                                        |
| 13  | api_rest             | done   |                                                                        |
| 14  | api_websocket        | done   |                                                                        |
| 15  | celery_workers       | done   |                                                                        |
| 16  | frontend_base        | done   |                                                                        |
| 17  | frontend_map         | done   |                                                                        |
| 18  | frontend_hud         | done   |                                                                        |
| 19  | backend_review_fixes | done   | Code review fixes: agent state machine, services, API, engine, physics |
| 20  | critical_bug_fixes   | done   | 11 critical bugs fixed: WorldState crash, API endpoints, agent system, engine commit, route creation |

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
- [16_frontend_base] `tsconfig.json` — removido `ignoreDeprecations: "6.0"` (inválido no TS 5.x), `baseUrl` e `paths` (alias `@/*` não utilizado). Adicionado `vite-env.d.ts` para tipagem de `import.meta.env`.
- [17_frontend_map] `react-map-gl` v8 adicionado como dependência para integração MapLibre + deck.gl. `WorldStatePayload` estendido com `active_routes?: ActiveRoute[]` (opcional) e `worldStore` recebe `activeRoutes` — rotas chegam vazias até o backend incluir rotas no payload.
- [17_frontend_map] `Map` de `react-map-gl/maplibre` renomeado para `MapGL` no import para evitar shadowing do global `Map` constructor.
- [19_backend_review_fixes] `perceive_node` convertido de função standalone para factory `_make_perceive_node(db_session)` — corrige crash por `AsyncSession()` sem bind.
- [19_backend_review_fixes] `fast_path` agora redireciona para `act` em vez de `END` — decisões fast-path são validadas por guardrails e persistidas no banco.
- [19_backend_review_fixes] Ação `emergency_order` substituída por mapa `_EMERGENCY_ACTION_MAP` por entity_type — `store→order_replenishment`, `warehouse→request_resupply`, `factory→start_production`.
- [19_backend_review_fixes] `master_agent.run_master_cycle` (dead code) removido; `evaluate_chaos` substituído de LLM call por lógica determinística via `ChaosService.can_inject_autonomous_event()`.
- [19_backend_review_fixes] Engine agora busca rota via `RouteRepository.get_active_by_truck()` em vez de acessar `truck.active_route` — resolve N+1 e lazy loading issues.
- [19_backend_review_fixes] `route.eta_ticks` agora é decrementado a cada tick no engine — corrige bug onde caminhões nunca chegavam ao destino.
- [19_backend_review_fixes] 5 services stub implementados: `WorldStateService`, `SimulationService`, `TriggerEvaluationService`, `RouteService`, `PhysicsService`.
- [19_backend_review_fixes] 6 dependency factories implementadas em `api/dependencies.py` — todas as rotas API agora funcionais.
- [19_backend_review_fixes] CORS corrigido: `allow_origins=["*"]` com `allow_credentials=True` substituído por origins configuráveis via env `CORS_ORIGINS`.
- [20_critical_bug_fixes] `world_state.py` — removido `t.name` (Truck DB sem coluna `name`), adicionado `base_lat`/`base_lng` (campos obrigatórios no TruckEntity), removido `s.region` (Store DB sem coluna `region`).
- [20_critical_bug_fixes] `api/routes/world.py` — `service.get_snapshot()` corrigido para `service.load()` (método real do WorldStateService).
- [20_critical_bug_fixes] `main.py` lifespan — `SimulationEngine` + `SimulationService` inicializados com `WorldStateService`, Redis client e `AsyncSessionLocal`. Graceful shutdown adicionado.
- [20_critical_bug_fixes] `api/routes/simulation.py` + `world.py` — removido `await` de `get_status()` e `set_tick_interval()` (métodos sync que retornam dict).
- [20_critical_bug_fixes] `master_agent.py` — `ChaosService.__new__()` substituído por instanciação correta com `EventRepository` + `AsyncSession` via `AsyncSessionLocal`.
- [20_critical_bug_fixes] `agents/base.py` — placeholders `{world_state_summary}`, `{decision_history}`, `{truck_type}` agora substituídos com dados reais. Funções `_format_world_state_summary()` e `_format_decision_history()` adicionadas.
- [20_critical_bug_fixes] `agents/base.py` `_act_node` — `entity_type` corrigido para `agent_type` (nome real da coluna em `AgentDecision`), `event_type` adicionado (coluna NOT NULL que faltava).
- [20_critical_bug_fixes] `simulation/engine.py` `_apply_physics` — `await session.commit()` adicionado ao final; sem ele, todas as escritas de physics eram descartadas por rollback implícito.
- [20_critical_bug_fixes] `services/route.py` `create_route` — assinatura e dict corrigidos para `origin_type`+`origin_id`+`dest_type`+`dest_id`+`started_at`; removido `distance_km` (coluna inexistente) e `destination_id` (campo errado).
