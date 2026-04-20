# Feature 30 — Integration Tests: Invariants, Event Chains, and Edge Cases

## Objetivo

Segunda passada de varredura forense após a feature 29. A F29 validou o happy path do ciclo completo (store → warehouse → factory → truck → delivery) e corrigiu 7 bugs reais. A F30 foca em três blocos **não cobertos** pelos testes anteriores: invariantes globais que devem valer tick-a-tick (conservação de estoque, não-negatividade, referências consistentes), cadeias de eventos produzidas pela engine (`resupply_delivered`, `truck_arrived`, `engine_blocked_degraded_truck`) e edge cases (deleção em cascata com estoque reservado, stop_production mid-flight, crash de agente, guardrail semântico, zombie/orphan states).

Esta feature também **fortalece** tolerâncias frouxas em testes existentes do Bloco G (F29) — trocar `>=` e `abs(...) < 1.0` por igualdades exatas com cálculo determinístico de `demand_rate` e `production_rate` por tick. Além disso, confirma e corrige 5 bugs suspeitos identificados no review pós-F29 (BUG-30-1 a BUG-30-5).

Esta é a última feature de hardening antes de considerar o ciclo de simulação production-ready.

### Princípios

- **Invariantes por tick:** cada teste que valida conservação/não-negatividade assert a cada tick, não apenas no estado final.
- **Banco real:** PostgreSQL via testcontainers.
- **LLM mockada** via `RoutingFakeLLM` / `make_entity_routing_llm` / `make_combined_routing_llm` (conftest.py de `simulation/`).
- **Valhalla mockado** via fixture `mock_valhalla`. Redis mockado via `mock_redis`.
- **TDD estrito:** teste deve falhar se o bug existir na aplicação. Quando o bug for confirmado, o fix entra na Fase 2.

---

## Critérios de Aceitação

### Bloco A — Invariantes Globais

Arquivo: `backend/tests/integration/simulation/test_invariants.py`

- [ ] `test_stock_conservation_store_to_warehouse_transit` — durante trânsito warehouse→store, `sum(warehouse.stock + cargo.qty + store.stock) - store.demand_rate * ticks` permanece constante tick-a-tick.
- [ ] `test_stock_conservation_factory_to_warehouse_transit` — durante trânsito factory→warehouse, `sum(factory.stock + cargo.qty + warehouse.stock) - factory.production_rate * ticks` permanece constante tick-a-tick.
- [ ] `test_stock_reserved_never_exceeds_stock_per_tick` — warehouse com stock=40 recebendo 2 confirms concorrentes (30 ton cada): assert `stock_reserved <= stock` a cada tick.
- [ ] `test_factory_stock_reserved_never_exceeds_stock_per_tick` — factory com stock=400 atendendo resupply de 100 ton: assert `stock_reserved <= stock` a cada tick.
- [ ] `test_stock_never_negative` — cycle completo; após cada tick, toda entity tem `stock >= 0` e `stock_reserved >= 0`.
- [ ] `test_store_demand_caps_at_zero_stock` — store com stock=0.5, demand_rate=7.5: após 1 tick, stock==0 (não -7). Verifica `min(demand_rate, stock)` no physics.
- [ ] `test_truck_active_route_id_points_to_existing_route` — quando `trucks.active_route_id IS NOT NULL`, route existe e tem `truck_id == this.id`.
- [ ] `test_route_order_id_points_to_existing_order` — quando `routes.order_id IS NOT NULL`, a order existe.
- [ ] `test_no_duplicate_active_routes_per_truck` — query `SELECT truck_id FROM routes WHERE status='active' GROUP BY truck_id HAVING COUNT(*) > 1` retorna 0 linhas ao longo do ciclo.
- [ ] `test_truck_cargo_matches_route_order` — truck IN_TRANSIT: `cargo.order_id == route.order_id`.
- [ ] `test_truck_cargo_origin_matches_route_origin` — `cargo.origin_type == route.origin_type` e `cargo.origin_id == route.origin_id`.

### Bloco B — Cadeias de Eventos

Arquivo: `backend/tests/integration/simulation/test_event_chains.py`

- [ ] `test_resupply_delivered_event_created_on_warehouse_arrival` — truck entrega em warehouse: query `events` tem `event_type='resupply_delivered', entity_type='warehouse', entity_id=<dest>, status='active'`.
- [ ] `test_resupply_delivered_triggers_warehouse_agent_next_tick` — após delivery + 1 tick: `agent_decisions` tem decision de warehouse com `event_type='resupply_delivered'`.
- [ ] `test_resupply_delivered_triggers_store_agent_next_tick` — idem para delivery em store.
- [ ] `test_truck_arrived_event_created_on_arrival` — após delivery: event `truck_arrived` criado para `entity_type='truck', entity_id=<truck>`.
- [ ] `test_truck_arrived_triggers_truck_agent` — após delivery + 1 tick: truck agent executou com `event_type='truck_arrived'`.
- [ ] `test_engine_blocked_event_published_to_redis` — truck com degradation>=0.95 IN_TRANSIT. Após tick: `mock_redis.publish` chamado com canal `nexus:events` e data contendo `engine_blocked_degraded_truck`.
- [ ] `test_send_stock_with_owned_truck_emits_new_order` — factory-003 com truck-002 proprietário idle; send_stock emite evento `new_order` para truck-002.
- [ ] `test_send_stock_fallback_to_contract_proposal` — factory sem truck proprietário idle: emite `contract_proposal` para truck terceiro.

### Bloco C — Deletion Cascade e Zombie Stock

Arquivo: `backend/tests/integration/simulation/test_deletion_cascade.py`

- [ ] `test_store_deletion_releases_warehouse_reserved_stock` — store-001 com order confirmed 30 ton; warehouse-002 `stock_reserved=30`. DELETE store-001 → `stock_reserved` volta a 0.
- [ ] `test_factory_deletion_releases_factory_reserved_stock` — warehouse-002 com order confirmed para factory-003 (100 ton); factory `stock_reserved=100`. DELETE warehouse-002 → factory `stock_reserved=0`.
- [ ] `test_warehouse_deletion_releases_upstream_factory_reserved` — mesmo que acima, apagando o warehouse enquanto ele ainda espera a factory.
- [ ] `test_truck_in_transit_to_deleted_store_handles_gracefully` — truck IN_TRANSIT para store-001; DELETE store-001; quando ETA expira: engine não crasha, rota marcada como `interrupted` (ou `cancelled`), cargo descartado, truck volta a `idle`.
- [ ] `test_truck_in_transit_from_deleted_warehouse` — truck IN_TRANSIT partindo de warehouse deletado: engine não crasha, rota é encerrada, truck `idle`.
- [ ] `test_order_cancelled_releases_reserved` — order confirmed; DELETE requester via API → target.stock_reserved volta a 0.

### Bloco D — Stop Production e In-Flight Orders

Arquivo: `backend/tests/integration/simulation/test_stop_production.py`

- [ ] `test_stop_production_does_not_affect_in_transit_order` — send_stock criou order + truck IN_TRANSIT; factory emite `stop_production`. Asserts: `production_rate_current==0`, order em trânsito completa, warehouse recebe estoque, `factory.stock_reserved` volta a 0 sem ficar negativo.
- [ ] `test_stop_production_rejects_new_resupply_from_empty_factory` — factory com cimento=0, production=0; warehouse pede 100 ton. `atomic_reserve_stock` falha (`stock - stock_reserved < 100`): nenhum order criado, nenhuma reserva feita.

### Bloco E — Concurrency Edge Cases

Arquivo: `backend/tests/integration/simulation/test_concurrency_edges.py`

- [ ] `test_factory_concurrent_send_stock_to_two_warehouses` — factory-003 stock=400; warehouse-001 e warehouse-002 pedem 100 ton cada no mesmo tick. Após processamento: `factory.stock_reserved==200` (soma exata das reservas), sem duplicação.
- [ ] `test_store_with_multiple_low_materials_triggers_once_per_tick` — store-001 com 3 materiais abaixo de reorder no mesmo tick. Engine flag `triggered=True` limita a 1 decisão por tick: exatamente 1 `agent_decisions` row de store-001 por tick.
- [ ] `test_two_confirms_in_same_tick_only_one_reserves` — 2 stores com pending orders no tick N-1; no tick N warehouse agent recebe 2 `order_received` triggers mas retorna confirm_order para apenas 1 (LLM programada). Apenas uma ordem fica `confirmed`; a outra permanece pending ou vira rejected — sem double reserve.

### Bloco F — Error Recovery e Guardrail Depth

Arquivo: `backend/tests/integration/simulation/test_guardrail_depth.py`

- [ ] `test_confirm_order_with_wrong_warehouse_is_rejected` — warehouse-002 tenta confirm_order cujo `target_id` é warehouse-001. Handler rejeita (ou falha silenciosamente); `warehouse-001.stock_reserved` e `warehouse-002.stock_reserved` permanecem inalterados.
- [ ] `test_accept_contract_for_delivered_order_is_noop` — truck LLM aceita order com status='delivered'. Handler detecta e não cria nova rota; truck permanece idle.
- [ ] `test_send_stock_with_wrong_material_fails_cleanly` — factory emite send_stock para material que ela não produz. Handler/guardrail rejeita; nenhuma reserva feita.
- [ ] `test_warehouse_agent_crash_does_not_leave_stock_reserved` — LLM passa no guardrail mas causa crash no handler (mock `_handle_confirm_order` → exception). Assert: `warehouse.stock_reserved` não foi incrementado (transação revertida).
- [ ] `test_partial_effect_rolled_back_on_exception` — falha em `_dispatch_truck_for_order` após order confirmed. Após rollback: order volta a pending, `stock_reserved` volta a 0.

### Bloco G — Fortalecimento de Tolerâncias (arquivos existentes)

Editar os testes listados — substituir `>=`, `>`, `abs(...) < X` por igualdades exatas usando `demand_rate` e `production_rate` determinísticos. **Não criar novos arquivos.**

- [ ] `test_full_cycle.py::test_stock_transferred_to_store_on_arrival` — substituir `abs(...) < 1.0` por `== expected_exact` (30 + initial − demand_rate × ticks_in_transit).
- [ ] `test_full_cycle.py::test_warehouse_reserves_stock_on_confirm` — substituir `>= 30.0` por `== 30.0`.
- [ ] `test_full_cycle.py::test_full_cycle_store_to_delivery` — substituir `final_store > initial_store` por `== expected_exact`.
- [ ] `test_rescue_mission.py::test_rescue_truck_accepts_and_delivers` — substituir `final_store > initial` por `== 50 - demand_consumed_exact`.
- [ ] `test_transport_retry.py::test_confirmed_order_not_lost` — adicionar assert `warehouse.stock_reserved == 30` durante toda a espera.

### Bloco H — Scenarios that should NEVER happen

Arquivo: `backend/tests/integration/simulation/test_zombie_states.py`

- [ ] `test_no_confirmed_order_without_stock_reserved` — run cycle; para toda order `status='confirmed'`: `target.stock_reserved >= order.quantity_tons` verificado continuamente.
- [ ] `test_no_pending_order_with_retry_after_tick` — `status='pending' AND retry_after_tick IS NOT NULL` é estado inconsistente. Query não retorna linhas em nenhum tick do cycle.
- [ ] `test_broken_truck_cannot_accept_contract` — truck `status='broken'` recebe contract_proposal; LLM retorna `accept_contract`. Handler rejeita (ConflictError capturado); truck permanece broken sem route atribuída.

### Backend — Correção de Bugs Confirmados

- [ ] **BUG-30-1** (`src/repositories/order.py::bulk_cancel_by_requester` e `bulk_cancel_by_target`): antes de cancelar orders `confirmed`, iterar e chamar `release_reserved` no target/requester correspondente (warehouse/factory). Services `StoreService.delete`, `WarehouseService.delete`, `FactoryService.delete` devem coordenar a liberação.
- [ ] **BUG-30-2** (`src/services/decision_effect_processor.py::_handle_accept_contract`): quando `assign_route` levanta `ConflictError` (truck em `broken`/`maintenance`), o handler deve logar e propagar ou ignorar limpa sem efeitos colaterais (cargo/route). Validar que truck permanece íntegro.
- [ ] **BUG-30-3** (`src/simulation/engine.py::_apply_physics` delivery path): ao chegar em destino inexistente (store/warehouse/factory deletado durante o trânsito), pular transfer de stock, marcar route como `cancelled` (ou `interrupted`), limpar cargo e enviar truck a idle. Sem crash.
- [ ] **BUG-30-4** (`src/simulation/engine.py::_evaluate_triggers`): eventos `truck_arrived` e `resupply_delivered` devem ser resolvidos (`event_repo.resolve`) no mesmo tick em que disparam o agente — não acumular na tabela.
- [ ] **BUG-30-5** (Bloco G): tolerâncias frouxas removidas conforme lista acima.

### Execução

- [ ] `pytest backend/tests/integration/simulation/ -v --timeout=180` passa 100% dos testes.
- [ ] Total de testes integration/simulation passando ≥ 85 (atual 71; meta +14–18).
- [ ] Suíte unitária (`pytest backend/tests/unit/`) continua passando (588 tests).

---

## Fora do Escopo

- Testes de WebSocket/dashboard (cobertos por F14 / F16–F18).
- Performance e benchmarking do engine (não há feature planejada).
- Testes de UI do frontend (não há feature planejada).
- Reescrita estrutural de `DecisionEffectProcessor` — apenas fixes pontuais dos bugs BUG-30-1 a BUG-30-4.
- Migrations de schema — os fixes dos bugs não alteram tabelas.
- Chaos engineering autônomo ou testes com Valhalla real (geo stack mockada).
- Rewriting de prompts de agentes.
