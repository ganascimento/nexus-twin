# Feature 30 — Integration Tests: Invariants, Event Chains, and Edge Cases

## Objetivo

Segunda passada de varredura forense apos feature 29. Foca em tres blocos nao cobertos:

1. **Invariantes que devem valer a cada tick** — conservacao de estoque, nao-negatividade, consistencia de referencias.
2. **Cadeias de eventos** — eventos produzidos pela engine (`resupply_delivered`, `truck_arrived`, `engine_blocked_degraded_truck`) sao consumidos?
3. **Edge cases e falhas parciais** — delecao em cascata com estoque reservado, corrupted states, stop_production mid-flight.

A feature 29 validou o happy path e alguns bugs. Esta feature 30 valida que o sistema **nao corrompe estado** em cenarios raros mas reais.

### Principios

- **Invariantes por tick:** a cada tick, os asserts de invariante devem valer. Teste verifica tick-a-tick, nao so no final.
- **LLM sempre mockada** via `RoutingFakeLLM`.
- **Valhalla sempre mockado.** Redis mockado.
- **Testes devem falhar se a aplicacao tiver o bug.** Se o teste for bom e a aplicacao falhar, o bug esta na aplicacao.

---

## Bloco A — Invariantes Globais (sempre validos)

### Cenario A1 — Conservacao de estoque durante transito

Enquanto um truck esta IN_TRANSIT com cargo: `origin.stock + cargo.quantity_tons + destination.stock` deve permanecer constante entre o tick de despacho e o tick de chegada (ajustado por `demand_rate` em stores e `production_rate_current` em factories, ambos deterministicos).

**Testes:**
- [ ] `test_stock_conservation_store_to_warehouse_transit` — warehouse cimento=150, cargo=30 em transito para store. Para cada tick ate chegada: `sum(warehouse.stock + cargo.qty + store.stock) - store.demand_rate * ticks == 150 + store_initial`.
- [ ] `test_stock_conservation_factory_to_warehouse_transit` — factory stock=400, cargo=100. `sum(factory.stock + cargo.qty + warehouse.stock) - factory.production_rate * ticks == 400 + wh_initial`.

### Cenario A2 — Invariante stock_reserved <= stock em cada tick

**Testes:**
- [ ] `test_stock_reserved_never_exceeds_stock_per_tick` — 2 stores pedem ao mesmo warehouse (40 ton, 2x30 demandados). A cada tick ao longo do cycle, assert `stock_reserved <= stock`. Deve valer ate mesmo durante tick onde dois confirms sao tentados concorrentemente.
- [ ] `test_factory_stock_reserved_never_exceeds_stock_per_tick` — warehouse pede 100, factory tem 400. A cada tick: `factory.stock_reserved <= factory.stock`.

### Cenario A3 — Non-negativity invariants

**Testes:**
- [ ] `test_stock_never_negative` — rodar cycle completo e verificar apos cada tick que toda entity tem `stock >= 0` e `stock_reserved >= 0`. Vale para store, warehouse, factory.
- [ ] `test_store_demand_caps_at_zero_stock` — store com stock=0.5 e demand_rate=7.5. Apos 1 tick: stock=0, nao -7. Verificar que physics usa `min(demand_rate, stock)`.

### Cenario A4 — Referencias consistentes

**Testes:**
- [ ] `test_truck_active_route_id_points_to_existing_route` — quando `trucks.active_route_id IS NOT NULL`, a route existe e tem `truck_id == this.id`.
- [ ] `test_route_order_id_points_to_existing_order` — quando `routes.order_id IS NOT NULL`, a order existe.
- [ ] `test_no_duplicate_active_routes_per_truck` — truck nao pode ter mais que uma route `active` ao mesmo tempo. Assert `SELECT truck_id, COUNT(*) FROM routes WHERE status='active' GROUP BY truck_id HAVING COUNT(*) > 1` retorna 0 linhas.

### Cenario A5 — Consistencia cargo <-> route

**Testes:**
- [ ] `test_truck_cargo_matches_route_order` — quando truck esta IN_TRANSIT, `truck.cargo->>'order_id' == route.order_id` para a rota ativa. Mismatch = bug.
- [ ] `test_truck_cargo_origin_matches_route_origin` — `cargo.origin_type == route.origin_type` e `cargo.origin_id == route.origin_id`.

---

## Bloco B — Cadeias de Eventos

### Cenario B1 — `resupply_delivered` deve triggerar destino

Quando um truck entrega em um warehouse (`route.dest_type='warehouse'`), a engine cria um evento `resupply_delivered`. No proximo tick, o warehouse agent deve ser acordado com esse trigger.

**Testes:**
- [ ] `test_resupply_delivered_event_created_on_warehouse_arrival` — apos delivery para warehouse, query events: assert `event_type='resupply_delivered', entity_type='warehouse', entity_id=<dest>, status='active'`.
- [ ] `test_resupply_delivered_triggers_warehouse_agent_next_tick` — LLM routed para warehouse-002 com response predeterminada. Apos delivery + 1 tick: `agent_decisions` tem decision de warehouse-002 com event_type='resupply_delivered'.
- [ ] `test_resupply_delivered_triggers_store_agent_next_tick` — mesmo para delivery em store.

### Cenario B2 — `truck_arrived` trigger

**Testes:**
- [ ] `test_truck_arrived_event_created_on_arrival` — apos delivery: event `truck_arrived` criado para `entity_type='truck', entity_id=<truck>`.
- [ ] `test_truck_arrived_triggers_truck_agent` — apos delivery + 1 tick: truck agent executou com event_type='truck_arrived'.

### Cenario B3 — `ENGINE_BLOCKED_DEGRADED_TRUCK` published

**Testes:**
- [ ] `test_engine_blocked_event_published_to_redis` — truck com degradation>=0.95 IN_TRANSIT. Apos tick: assert `mock_redis.publish` foi chamado com canal contendo o event_type ou data.

### Cenario B4 — `new_order` vs `contract_proposal` branching

Engine `_handle_send_stock` escolhe `new_order` se truck.factory_id == entity_id, senao `contract_proposal`.

**Testes:**
- [ ] `test_send_stock_with_owned_truck_emits_new_order` — factory-003 tem truck-002 como proprietario. send_stock: evento = `new_order` para truck-002.
- [ ] `test_send_stock_fallback_to_contract_proposal` — factory sem truck proprietario idle: evento = `contract_proposal` para truck terceiro.

---

## Bloco C — Deletion Cascade e Zombie State

### Cenario C1 — Store deletada com pedido confirmed deixa estoque reservado no warehouse

**CONFIRMAR BUG:** `bulk_cancel_by_requester` so atualiza `status='cancelled'` — nao chama `release_reserved`. Se a store for deletada com order confirmed (warehouse ja reservou), o warehouse fica com stock_reserved "zombie" nao liberado.

**Testes:**
- [ ] `test_store_deletion_releases_warehouse_reserved_stock` — store-001 com order confirmed 30 ton. Warehouse-002 stock_reserved=30. DELETE store -> stock_reserved deve voltar a 0.
- [ ] `test_factory_deletion_releases_factory_reserved_stock` — warehouse-002 com order confirmed para factory-003 (100 ton). Factory stock_reserved=100. DELETE warehouse -> factory stock_reserved=0.

### Cenario C2 — Truck ativo quando destino e deletado

**Testes:**
- [ ] `test_truck_in_transit_to_deleted_store_handles_gracefully` — truck IN_TRANSIT para store-001. DELETE store-001. Apos eta expira: truck nao crasha o engine; sua rota e marcada como `interrupted` ou cancelled; cargo e descartado ou redirigido; truck volta a idle.
- [ ] `test_truck_in_transit_from_deleted_warehouse` — truck IN_TRANSIT de warehouse deletada. Sistema nao crasha.

### Cenario C3 — Cancellation libera stock_reserved

**Testes:**
- [ ] `test_order_cancelled_releases_reserved` — order confirmed, depois cancelada via API DELETE requester. Stock_reserved do target retorna a 0.

---

## Bloco D — Stop Production e In-Flight Orders

### Cenario D1 — Factory para producao mas tem order confirmed em transito

Se factory emite `stop_production` para cimento mas ha uma order confirmed ja despachada (truck IN_TRANSIT com cargo), a order em transito deve completar normalmente.

**Testes:**
- [ ] `test_stop_production_does_not_affect_in_transit_order` — send_stock criou order + truck IN_TRANSIT. Factory emite `stop_production`. Assert:
  - `production_rate_current` = 0
  - Order em transito chega normalmente
  - Warehouse recebe estoque
  - `factory.stock_reserved` vai a 0 corretamente apos delivery (nao negativo)

### Cenario D2 — Factory para producao e warehouse pede resupply

**Testes:**
- [ ] `test_stop_production_rejects_new_resupply_from_empty_factory` — factory com cimento=0, production=0 (stopped), warehouse pede 100 ton. send_stock deve falhar em `atomic_reserve_stock` (`stock - stock_reserved < 100`) -> nenhum order criado, evento de log registrado.

---

## Bloco E — Concurrency Edge Cases

### Cenario E1 — Mesma factory com dois send_stock para warehouses diferentes no mesmo tick

**Testes:**
- [ ] `test_factory_concurrent_send_stock_to_two_warehouses` — factory-003 cimento=400. Warehouse-001 e Warehouse-002 ambos sem cimento pedindo 100 ton cada. Factory programada para responder send_stock a ambos. Assert: `factory.stock_reserved == 200` (soma das duas reservas), nenhuma fica duplicada.

### Cenario E2 — Multiple low-stock triggers para o mesmo store em stocks diferentes

**Testes:**
- [ ] `test_store_with_multiple_low_materials_triggers_once_per_tick` — store-001 com cimento=1, tijolos=0.5, vergalhao=10 (todos abaixo de reorder). Engine flag `triggered = True` deve limitar a 1 trigger por store por tick. Assert: exatamente 1 `agent_decisions` row de store-001 por tick.

### Cenario E3 — Real concurrent confirm (fortalecer test_concurrency)

**Testes:**
- [ ] `test_two_confirms_in_same_tick_only_one_reserves` — 2 stores ja com pending orders no tick N-1. No tick N, warehouse agent aparece apenas UMA VEZ mas recebe 2 order_received triggers. Garantir que apenas uma ordem fica confirmed (a segunda deve ficar pending ou rejected).

---

## Bloco F — Error Recovery e Guardrail Depth

### Cenario F1 — Guardrail rejects decisions beyond syntax

**Testes:**
- [ ] `test_confirm_order_with_wrong_warehouse_is_rejected` — warehouse-002 LLM response confirma order cujo `target_id` e warehouse-001 (nao pertence a esse agent). Handler deve rejeitar (ou falhar silenciosamente) sem corromper stock_reserved.
- [ ] `test_accept_contract_for_delivered_order_is_noop` — truck LLM response aceita order com status='delivered'. Handler deve detectar e nao tentar criar nova rota.
- [ ] `test_send_stock_with_wrong_material_fails_cleanly` — factory LLM responde send_stock para material que ela nao produz. Guardrail/handler deve rejeitar; nenhuma reserva feita.

### Cenario F2 — Agent crash mid-cycle

**Testes:**
- [ ] `test_warehouse_agent_crash_does_not_leave_stock_reserved` — warehouse LLM retorna resposta que passa no guardrail mas causa crash no handler. Assert stock_reserved do warehouse nao foi incrementado.
- [ ] `test_partial_effect_rolled_back_on_exception` — simular falha no `_dispatch_truck_for_order` apos order foi confirmed. Transaction deve rollback: order volta a pending, stock_reserved volta a 0.

---

## Bloco G — False-positives Remanescentes (Fortalecer)

Tests existentes com tolerancias frouxas que devem virar `==`:

| Teste | Problema atual | Fix |
|-------|---------------|-----|
| `test_full_cycle.py::test_stock_transferred_to_store_on_arrival` | Usa `abs(...) < 1.0` (tolerancia de 1 ton!) | Trocar por `==` exato com calculo deterministico de demand |
| `test_full_cycle.py::test_warehouse_reserves_stock_on_confirm` | `reserved >= 30.0` (>=) | Trocar por `== 30.0` |
| `test_full_cycle.py::test_full_cycle_store_to_delivery` | `final_store > initial_store` | Trocar por `final_store == expected` (calculo exato) |
| `test_rescue_mission.py::test_rescue_truck_accepts_and_delivers` | `final_store > initial` | Assert quantidade exata (50 - demand_consumed) |
| `test_transport_retry.py::test_confirmed_order_not_lost` | Assert apenas status | Adicionar: `stock_reserved` do warehouse permaneceu 30 durante a espera |

---

## Bloco H — Scenarios that should NEVER happen

### Cenario H1 — Zombie order detection

**Testes:**
- [ ] `test_no_confirmed_order_without_stock_reserved` — para toda order `confirmed`, o target deve ter `stock_reserved >= order.quantity_tons`. Invariante: run ticks completos e verificar continuamente.
- [ ] `test_no_pending_order_with_retry_after_tick` — `pending` + `retry_after_tick IS NOT NULL` = estado inconsistente. Qualquer order com esse par deve ser consertada.

### Cenario H2 — Broken trucks never accept contracts

**Testes:**
- [ ] `test_broken_truck_cannot_accept_contract` — truck status='broken' recebe contract_proposal e LLM programada responde `accept_contract`. Handler deve rejeitar (ConflictError caught) sem mudar state do truck.

---

## Estrutura de Arquivos

```
backend/tests/integration/simulation/
├── test_invariants.py           # Bloco A — conservacao e nao-negatividade
├── test_event_chains.py         # Bloco B — resupply_delivered, truck_arrived, engine_blocked
├── test_deletion_cascade.py     # Bloco C — delete cascade, stock_reserved liberado
├── test_stop_production.py      # Bloco D — stop_production mid-flight
├── test_concurrency_edges.py    # Bloco E — real concurrency, multi-trigger
├── test_guardrail_depth.py      # Bloco F — semantic rejections, crash recovery
├── test_zombie_states.py        # Bloco H — orphan/invalid state detection
```

Fortalecer (nao criar):
- test_full_cycle.py, test_rescue_mission.py, test_transport_retry.py — Bloco G

---

## Bugs Provaveis a Confirmar

Identificados durante o review. Os testes desta feature devem falhar se os bugs existem (TDD).

### BUG-30-1 — `bulk_cancel_by_requester/target` nao libera stock_reserved

**Local:** `src/repositories/order.py:160` e `src/services/store.py:39`, `src/services/factory.py:39`, `src/services/warehouse.py:39`.

**Sintoma:** deletar store/factory/warehouse com orders confirmed deixa stock_reserved zombie em warehouses/factories que ja reservaram estoque.

**Fix esperado:** antes de cancelar, iterar orders `confirmed` e chamar `release_reserved` no target/requester correspondente.

### BUG-30-2 — Broken truck pode aceitar contrato (exception silenciada)

**Local:** `src/services/decision_effect_processor.py::_handle_accept_contract`, `src/services/truck.py::assign_route`.

**Sintoma:** `assign_route` checa `status not in (idle, evaluating)` — `broken` nao esta na lista -> raises ConflictError. Bom em teoria, mas a exception e silenciada pelo try/except do processor. Cargo/route ainda podem ser afetados em outros pontos (investigar).

### BUG-30-3 — Truck em rota para entidade deletada

**Local:** `src/simulation/engine.py::_apply_physics` (delivery path).

**Sintoma:** se store/warehouse de destino foi deletado durante o transito, `update_stock` do destino viola FK ou retorna nada. Engine nao tem guard.

**Fix esperado:** skip stock transfer se destino nao existe, mark route as cancelled, send truck to idle.

### BUG-30-4 — Eventos `truck_arrived` e `resupply_delivered` podem nao ser consumidos

**Local:** `src/simulation/engine.py::_evaluate_triggers` usa `event_repo.get_active_for_entity` para cada entidade.

**Sintoma potencial:** eventos acumulam na tabela sem ser resolvidos se o agent nao emitir decisao que o processor saiba tratar.

### BUG-30-5 — Tolerancias frouxas em Bloco G mascaram bugs reais

**Local:** varios tests de `test_full_cycle.py`.

**Sintoma:** assertions usando `>` e `abs(...) < 1.0` permitem erros de 1 ton ou mais. Podem mascarar double-delivery, perda de carga, arredondamentos.

---

## Pre-requisitos

- Features 24-29 implementadas e testadas.
- `RoutingFakeLLM` e `RefreshingSession` disponiveis em conftest.

---

## Condicao de Conclusao

- Todos os testes do Bloco A-H passando.
- Bugs BUG-30-1 a BUG-30-5 confirmados e corrigidos (ou explicitamente marcados como nao-bugs).
- False positives do Bloco G fortalecidos (tolerances removidas).
- state.md atualizado documentando bugs corrigidos e decisoes de design.
- Total de testes integration simulation esperado: ~85-90 (atual: 71).
