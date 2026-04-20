# Tasks — Feature 30: Integration Tests Invariants and Edge Cases

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — TDD (§9), convenções (§8), constraints (§9)
- `.specs/features/30_integration_tests_invariants_and_edges/specs.md` — critérios e blocos A–H
- `.specs/state.md` — Implementation Decisions de F24–F29 (cargo origin/destination, consume_reserved, RoutingFakeLLM, RefreshingSession)
- `backend/tests/integration/simulation/conftest.py` — fixtures `seeded_simulation_client`, `mock_redis`, `mock_valhalla`, `advance_ticks_with_settle`, `RoutingFakeLLM`, `make_entity_routing_llm`, `make_combined_routing_llm`, `RefreshingSession`
- `backend/tests/integration/simulation/test_full_cycle.py` — padrão de multi-tick + LLM mockada
- `backend/tests/integration/simulation/test_rescue_mission.py`, `test_transport_retry.py` — padrões a fortalecer no Bloco G
- `backend/src/simulation/engine.py` — `_apply_physics`, `_evaluate_triggers`, `_dispatch_agent`
- `backend/src/services/decision_effect_processor.py` — handlers `_handle_send_stock`, `_handle_confirm_order`, `_handle_accept_contract`
- `backend/src/repositories/order.py` — `bulk_cancel_by_requester`, `bulk_cancel_by_target`
- `backend/src/repositories/warehouse.py`, `backend/src/repositories/factory.py` — `release_reserved`, `atomic_reserve_stock`, `consume_reserved`
- `backend/src/services/store.py`, `backend/src/services/warehouse.py`, `backend/src/services/factory.py` — métodos `delete`
- `.specs/prd.md` §4 — dados do seed (estoques, capacidades, reorder_points)

**Pré-requisito:** F24–F29 `done`. Testes novos vão falhar até os bugs BUG-30-1 a BUG-30-5 serem corrigidos — isso é esperado (TDD).

---

## Plano de Execução

**TDD aplica.** Fluxo em duas fases conforme CLAUDE.md §9.

- **Fase 1 — Testes (Grupos 1–3 em paralelo).** Escreve todos os 7 novos arquivos de teste + fortalece os 3 existentes. Pausa obrigatória para aprovação do usuário.
- **Fase 2 — Correção de Bugs (Grupos 4–7 após aprovação).** Corrige BUG-30-1 a BUG-30-4 (BUG-30-5 é o próprio Grupo 3 de testes). Grupos 4 e 5 em paralelo; Grupo 6 depende do 4 (services de delete usam os repositórios ajustados); Grupo 7 é a validação sequencial.

**Não escrever código de produção na Fase 1.** Stubs e `NotImplementedError` em arquivos de produção não são necessários — os bugs já existem no código, e os testes devem falhar até serem corrigidos.

---

### Fase 1 — Testes

### Grupo 1 — Bloco A + Bloco B (um agente)

**Tarefa:** Criar os testes de invariantes globais e cadeias de eventos.

1. Criar `backend/tests/integration/simulation/test_invariants.py` com todos os testes do Bloco A listados em `specs.md`:
   - Para `test_stock_conservation_*`: montar setup com store/warehouse/factory em estado conhecido; programar LLM via `make_entity_routing_llm` para disparar a cadeia; usar `advance_ticks_with_settle` tick-a-tick e assert a conservação após cada tick via `session` reaberta (`RefreshingSession`).
   - Para `test_stock_reserved_never_exceeds_stock_per_tick`: programar 2 stores pedindo ao mesmo warehouse; loop tick-a-tick consultando `warehouse_stocks.stock` e `stock_reserved` direto via `text("SELECT ...")`.
   - Para `test_stock_never_negative` e `test_store_demand_caps_at_zero_stock`: cycle completo com multiple ticks; assert queries agregadas em todas as tabelas de stock.
   - Para invariantes de referência (`test_truck_active_route_id_points_to_existing_route`, `test_route_order_id_points_to_existing_order`, `test_no_duplicate_active_routes_per_truck`): queries SQL diretas após o cycle.
   - Para `test_truck_cargo_matches_route_order` / `test_truck_cargo_origin_matches_route_origin`: após tick em que truck entra em trânsito, query `trucks.cargo` (JSONB) + `routes` e comparar campo a campo.

2. Criar `backend/tests/integration/simulation/test_event_chains.py` com todos os testes do Bloco B:
   - `test_resupply_delivered_event_created_on_warehouse_arrival`: cycle de delivery em warehouse; query `events` filtrando `event_type='resupply_delivered'`.
   - `test_resupply_delivered_triggers_warehouse_agent_next_tick`: programar LLM para warehouse-002 com resposta na queue; após delivery + 1 tick, query `agent_decisions` com `event_type='resupply_delivered'`.
   - `test_engine_blocked_event_published_to_redis`: forçar `trucks.degradation=0.95` antes do tick; assert `mock_redis.publish` chamado com payload contendo `engine_blocked_degraded_truck`.
   - `test_send_stock_with_owned_truck_emits_new_order` / `test_send_stock_fallback_to_contract_proposal`: programar factory-003 para responder send_stock; verificar `events` gerados (`new_order` vs `contract_proposal`) com base em disponibilidade de truck proprietário idle.

3. Usar sempre `mock_valhalla` + `mock_redis` das fixtures existentes. Não instanciar `RouteService` real.

4. Usar `RefreshingSession` para não cair em snapshots antigos após commit do engine.

---

### Grupo 2 — Bloco C + Bloco D + Bloco F + Bloco H (um agente)

**Tarefa:** Criar os testes de deletion cascade, stop_production, guardrail depth e zombie states.

1. Criar `backend/tests/integration/simulation/test_deletion_cascade.py` (Bloco C):
   - `test_store_deletion_releases_warehouse_reserved_stock`: criar order confirmed (via engine real OU inserção direta no DB); DELETE store via API (`DELETE /stores/{id}`); após, `SELECT stock_reserved FROM warehouse_stocks WHERE warehouse_id=...` == 0.
   - `test_factory_deletion_releases_factory_reserved_stock`: análogo para factory como target.
   - `test_warehouse_deletion_releases_upstream_factory_reserved`: warehouse com order confirmed upstream (factory como target) + downstream (store como requester). Após DELETE warehouse, factory stock_reserved volta a 0.
   - `test_truck_in_transit_to_deleted_store_handles_gracefully` / `test_truck_in_transit_from_deleted_warehouse`: colocar truck IN_TRANSIT, DELETE destino/origem via API, avançar até ETA expirar; assert engine não crasha, `routes.status='interrupted'` ou `'cancelled'`, `trucks.status='idle'`, `trucks.cargo=null`.
   - `test_order_cancelled_releases_reserved`: criar order confirmed; `DELETE /stores/{requester}`; verificar `warehouse_stocks.stock_reserved==0`.

2. Criar `backend/tests/integration/simulation/test_stop_production.py` (Bloco D):
   - `test_stop_production_does_not_affect_in_transit_order`: programar factory-003 para `send_stock` no tick 1; avançar até truck IN_TRANSIT; programar factory-003 para `stop_production` no tick 2; avançar até delivery; asserts de stock em todos os momentos.
   - `test_stop_production_rejects_new_resupply_from_empty_factory`: setup factory cimento=0, `production_rate_current=0`; warehouse pede resupply; factory responde `send_stock` (LLM programada); `atomic_reserve_stock` deve retornar `False` — nenhuma order criada. Verificar query `pending_orders WHERE requester_id='warehouse-002' AND material_id='cimento'`.

3. Criar `backend/tests/integration/simulation/test_guardrail_depth.py` (Bloco F):
   - `test_confirm_order_with_wrong_warehouse_is_rejected`: warehouse-002 responde `confirm_order` com `target_id='warehouse-001'`. Após tick: `warehouse-001.stock_reserved==0` e `warehouse-002.stock_reserved==0`.
   - `test_accept_contract_for_delivered_order_is_noop`: pré-criar order com status='delivered' no DB; truck LLM responde accept_contract para ela; after tick: truck status=='idle', sem rotas ativas novas.
   - `test_send_stock_with_wrong_material_fails_cleanly`: factory-003 responde send_stock para `material_id='aco'` (não produz). After tick: nenhuma order criada, nenhuma reserva.
   - `test_warehouse_agent_crash_does_not_leave_stock_reserved`: mock `_handle_confirm_order` via `monkeypatch` para `raise RuntimeError`; warehouse LLM retorna confirm_order. After tick: `warehouse.stock_reserved==0`, decision NÃO persistida em `agent_decisions` (transação revertida).
   - `test_partial_effect_rolled_back_on_exception`: mock `_dispatch_truck_for_order` (ou `RouteService.compute_route`) para raise após `_handle_confirm_order` ter feito a reserva. After tick: order status='pending' e `stock_reserved==0`.

4. Criar `backend/tests/integration/simulation/test_zombie_states.py` (Bloco H):
   - `test_no_confirmed_order_without_stock_reserved`: cycle de 20 ticks; a cada tick, query `pending_orders WHERE status='confirmed'` e, para cada row, verificar `stock_reserved >= order.quantity_tons` no target.
   - `test_no_pending_order_with_retry_after_tick`: cycle completo incluindo rejeição + retry; a cada tick, query `SELECT 1 FROM pending_orders WHERE status='pending' AND retry_after_tick IS NOT NULL LIMIT 1` — deve retornar 0 linhas sempre.
   - `test_broken_truck_cannot_accept_contract`: forçar `UPDATE trucks SET status='broken' WHERE id='truck-004'`; programar truck LLM para accept_contract; after tick: `trucks.status='broken'`, `active_route_id IS NULL`, nenhuma rota nova criada.

5. **Regras comuns a todos os arquivos desta task:**
   - Valhalla: usar fixture `mock_valhalla`.
   - Redis: usar `mock_redis`.
   - LLM: usar `make_entity_routing_llm` ou `make_combined_routing_llm` conforme quantos agentes ativos há no tick.
   - Session: usar `RefreshingSession` para evitar snapshot obsoleto.
   - Nunca criar fixtures novas no conftest — reutilizar as existentes.

---

### Grupo 3 — Bloco G: Fortalecimento de Tolerâncias (um agente)

**Tarefa:** Editar 3 arquivos existentes para trocar tolerâncias frouxas por igualdades exatas.

1. `backend/tests/integration/simulation/test_full_cycle.py`:
   - `test_stock_transferred_to_store_on_arrival`: calcular `expected_final = 1.0 + 30.0 - demand_rate_per_tick * ticks_between_dispatch_and_arrival`. Trocar `abs(final - expected) < 1.0` por `final == pytest.approx(expected, abs=0.001)` — tolerância de 0.001 apenas para float arithmetic.
   - `test_warehouse_reserves_stock_on_confirm`: trocar `stock_reserved >= 30.0` por `stock_reserved == 30.0`.
   - `test_full_cycle_store_to_delivery`: trocar `final_store_stock > initial_store_stock` por `final_store_stock == pytest.approx(expected, abs=0.001)`.

2. `backend/tests/integration/simulation/test_rescue_mission.py`:
   - `test_rescue_truck_accepts_and_delivers`: calcular `expected = initial + 50 - demand_rate * ticks_consumed` e trocar `final > initial` por `final == pytest.approx(expected, abs=0.001)`.

3. `backend/tests/integration/simulation/test_transport_retry.py`:
   - `test_confirmed_order_not_lost`: além dos asserts existentes, adicionar loop tick-a-tick durante a espera assert `warehouse.stock_reserved == 30.0` via `text("SELECT stock_reserved FROM warehouse_stocks ...")`.

4. **Importante:** ler os `demand_rate` exatos do seed (`.specs/prd.md §4` ou `backend/src/database/seed.py`). Não hardcodar valores aproximados — o cálculo deve derivar do seed.

5. Rodar os três arquivos após as edições (`pytest backend/tests/integration/simulation/test_full_cycle.py test_rescue_mission.py test_transport_retry.py`) para confirmar que falham agora por bugs reais (não por bugs dos testes).

---

### Pausa obrigatória — Aprovação da Fase 1

Após Grupos 1–3 completarem, apresentar ao usuário a lista de testes criados/editados e **aguardar aprovação** antes de iniciar a Fase 2. Não executar os grupos seguintes sem "approved".

Durante a apresentação, listar também quais testes são esperados falhar (validam BUG-30-1 a BUG-30-5) e quais devem passar desde já (invariantes que já valem no código atual).

---

### Fase 2 — Correção dos Bugs

### Grupo 4 — BUG-30-1: Liberação de stock_reserved no cascade delete (um agente)

**Tarefa:** Ajustar repositórios e services para liberar estoque reservado antes de cancelar orders em cascata.

1. Editar `backend/src/repositories/order.py`:
   - `bulk_cancel_by_requester(requester_id)`: antes de `UPDATE ... SET status='cancelled'`, selecionar orders `WHERE requester_id=:id AND status='confirmed'`. Retornar lista `[(target_type, target_id, material_id, quantity_tons), ...]` para o caller.
   - `bulk_cancel_by_target(target_id)`: análogo — retornar lista `[(requester_type, requester_id, ...)]` para quem deve liberar reservas feitas.
   - Ambos os métodos mantêm a assinatura mas passam a retornar `List[CancelledOrderInfo]` (dataclass/namedtuple simples).

2. Editar `backend/src/services/store.py::StoreService.delete`:
   - Antes de `StoreRepository.delete`, chamar `OrderRepository.bulk_cancel_by_requester(store_id)`.
   - Para cada order retornada com `target_type='warehouse'`: chamar `WarehouseRepository.release_reserved(target_id, material_id, quantity_tons)`.

3. Editar `backend/src/services/warehouse.py::WarehouseService.delete`:
   - Antes de deletar, chamar `bulk_cancel_by_requester(warehouse_id)` (orders upstream para factory) e `bulk_cancel_by_target(warehouse_id)` (orders downstream pedidas por stores).
   - Para upstream com `target_type='factory'`: `FactoryRepository.release_reserved(target_id, material_id, qty)`.
   - Para downstream com status=confirmed: o próprio warehouse era o target — a reserva está no warehouse sendo deletado, então nada a liberar (vai junto).

4. Editar `backend/src/services/factory.py::FactoryService.delete`:
   - `bulk_cancel_by_target(factory_id)` — orders de warehouses pedindo ao factory. Nesses casos, a reserva era na factory (sendo deletada), nada a liberar adicional.
   - Não há orders onde factory seja requester (nossa convenção).

5. Sem migration de schema. Sem mudança em `api/routes/*.py` — os services delegam.

---

### Grupo 5 — BUG-30-3 e BUG-30-4: Engine handling de entidades deletadas e resolução de eventos (um agente, paralelo ao Grupo 4)

**Tarefa:** Ajustar `SimulationEngine._apply_physics` e `_evaluate_triggers` para não crashar em destino inexistente e resolver eventos corretamente.

1. Editar `backend/src/simulation/engine.py::_apply_physics` — delivery path:
   - Antes de chamar `StoreRepository.update_stock` / `WarehouseRepository.update_stock` no destino: verificar existência via `get_by_id(dest_id)`. Se retornar `None`:
     - Marcar `route.status='interrupted'` (ou `'cancelled'`, escolher baseado no enum existente — verificar `src/enums/routes.py`).
     - Limpar `truck.cargo = None`, `truck.active_route_id = None`.
     - Transicionar `truck.status='idle'`.
     - Logar warning.
     - Não tentar transferir stock.
     - Também liberar `stock_reserved` da origem se ainda houver (para não deixar zombie).
   - Análogo para origem inexistente (embora raro — truck pode estar em rota partindo de warehouse deletado enquanto a rota ainda é ativa).

2. Editar `backend/src/simulation/engine.py::_evaluate_triggers`:
   - Para eventos `truck_arrived` e `resupply_delivered`: após criar o trigger e fire `asyncio.create_task(agent.run_cycle(event))`, chamar `event_repo.resolve(event_id)` no **mesmo tick**. Atualmente isso já é feito para warehouse/store/truck (decisão de F26), mas verificar se cobre `truck_arrived` e `resupply_delivered` explicitamente — a specs marca este como BUG potencial. Se já estiver resolvido, marcar o teste como passing sem alteração.

3. Nenhuma mudança em schema. Ajustar apenas engine.

---

### Grupo 6 — BUG-30-2: accept_contract silently fails for broken truck (um agente, depende do Grupo 4)

**Tarefa:** Garantir que `_handle_accept_contract` em `DecisionEffectProcessor` trate corretamente trucks em `broken`/`maintenance`.

1. Editar `backend/src/services/decision_effect_processor.py::_handle_accept_contract`:
   - Antes de `TruckService.assign_route`, verificar `truck.status`. Se estiver em `broken` ou `maintenance`:
     - Log warning (`logger.warning("accept_contract rejected: truck is {status}")`).
     - Retornar sem efeitos colaterais — não criar cargo, não computar rota, não alterar order.
     - Order pode permanecer `confirmed` aguardando transport retry no próximo tick (já coberto por F27).
   - Se `ConflictError` for levantado por `assign_route` mesmo assim (race condition ou outro status), capturar e logar — sem propagar.

2. Sem schema changes. Sem mudança em `TruckService.assign_route` (a validação interna já existe).

---

### Grupo 7 — Validação final (sequencial, após Grupos 4–6)

**Tarefa:** Rodar suíte completa e confirmar critérios.

1. Rodar `pytest backend/tests/integration/simulation/ -v --timeout=180`. Confirmar ≥ 85 testes passando, zero falhas.
2. Rodar `pytest backend/tests/unit/ -q`. Confirmar 588+ testes passando.
3. Rodar `pytest backend/tests/ -q --timeout=180` (suíte completa) para confirmar integração.
4. Se algum teste falhar: diagnosticar se é bug de teste ou bug de produção. Corrigir o lado apropriado. Não marcar a feature como done com testes vermelhos.
5. Atualizar `.specs/state.md`:
   - Feature 30 status → `done`.
   - Notes: resumir testes adicionados, bugs corrigidos (BUG-30-1, BUG-30-2, BUG-30-3, BUG-30-4), tolerâncias apertadas no Bloco G.
6. Registrar em "Implementation Decisions" decisões não-óbvias (ex: formato de retorno de `bulk_cancel_*`, escolha entre `interrupted` e `cancelled` no Grupo 5).

---

## Condição de Conclusão

- Todos os critérios de `specs.md` verdes (Blocos A–H + Backend bugs + Execução).
- `pytest backend/tests/integration/simulation/` passa 100% com ≥ 85 testes.
- `pytest backend/tests/unit/` continua verde.
- BUG-30-1 a BUG-30-5 corrigidos e validados pelos testes da Fase 1.
- `.specs/state.md` atualizado: feature 30 → `done`, decisões registradas.
