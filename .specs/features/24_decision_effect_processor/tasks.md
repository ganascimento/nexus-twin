# Tasks — Feature 24: Decision Effect Processor

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — arquitetura MAS (§4.2), fluxo de decisao (§7), TDD (§9), convencoes (§8)
- `.specs/features/24_decision_effect_processor/specs.md` — criterios de aceitacao desta feature
- `backend/src/agents/base.py` — `_make_act_node_for_graph()`, `build_agent_graph()` — onde o processor sera integrado
- `backend/src/services/order.py` — `OrderService` metodos existentes: `create_order`, `confirm_order`, `reject_order`
- `backend/src/services/warehouse.py` — `WarehouseService.confirm_order()`, `reject_order()` — com reserva atomica
- `backend/src/services/factory.py` — `FactoryService.adjust_stock()`
- `backend/src/services/truck.py` — `TruckService.assign_route()`, `schedule_maintenance()`
- `backend/src/services/route.py` — `RouteService.compute_route()`, `create_route()`
- `backend/src/repositories/order.py` — `OrderRepository` metodos existentes
- `backend/src/database/models/order.py` — schema do `PendingOrder`
- `backend/src/guardrails/` — todos os arquivos, para entender os payloads validados de cada acao
- `backend/src/simulation/events.py` — tipos de evento para caminhoes

Nao leia specs de outras features. Nao modifique prompts nem guardrails.

---

## Plano de Execucao

**Fase 1 (TDD) — Grupo 1:** escrever todos os testes antes de qualquer implementacao. Parar e aguardar aprovacao.

**Fase 2 (Implementacao) — Grupos 2-5** apos aprovacao dos testes.

---

### Grupo 1 — Testes (FASE 1: TDD) PARAR AQUI

**Tarefa:** Escrever todos os testes unitarios do `DecisionEffectProcessor`. Nao escrever nenhum codigo de implementacao.

**Estrutura de pastas dos testes** (espelha `backend/src/services/`):

```
backend/tests/unit/services/
├── __init__.py
├── test_decision_effect_processor.py
```

Criar `backend/tests/unit/services/__init__.py` se nao existir.

**Fixtures** em `test_decision_effect_processor.py`:

- `mock_db_session` — `AsyncMock` de `AsyncSession`
- `mock_order_repo` — `AsyncMock` de `OrderRepository` com `has_active_order` retornando `False`, `create` retornando um `MagicMock(id=uuid4())`
- `mock_warehouse_service` — `AsyncMock` de `WarehouseService`
- `mock_factory_repo` — `AsyncMock` de `FactoryRepository`
- `mock_truck_service` — `AsyncMock` de `TruckService`
- `mock_route_service` — `AsyncMock` de `RouteService` com `compute_route` retornando `{"path": [...], "timestamps": [...], "distance_km": 100, "eta_ticks": 3}`
- `mock_event_repo` — `AsyncMock` de `EventRepository`
- `mock_truck_repo` — `AsyncMock` de `TruckRepository`
- `processor` — instancia de `DecisionEffectProcessor` com todos os mocks acima

**Testes a escrever:**

1. `test_process_hold_is_noop` — chama `processor.process("store", "store_01", "hold", {}, tick=5)` — nenhum service/repo e chamado
2. `test_process_unknown_action_logs_warning` — chama `processor.process("store", "store_01", "unknown_action", {}, tick=5)` — nao levanta excecao, nenhum service chamado
3. `test_order_replenishment_creates_pending_order` — chama com `("store", "store_01", "order_replenishment", {"material_id": "cimento", "quantity_tons": 20, "from_warehouse_id": "wh_01"}, tick=5)` — `mock_order_repo.create` chamado com `requester_type="store"`, `requester_id="store_01"`, `target_type="warehouse"`, `target_id="wh_01"`, `material_id="cimento"`, `quantity_tons=20`, `status="pending"`
4. `test_order_replenishment_deduplicates` — `mock_order_repo.has_active_order` retorna `True` — `mock_order_repo.create` **nao** e chamado
5. `test_confirm_order_calls_warehouse_service` — chama com `("warehouse", "wh_01", "confirm_order", {"order_id": "order_007", "quantity_tons": 50, "eta_ticks": 3}, tick=5)` — `mock_warehouse_service.confirm_order` chamado com `("order_007", 3)` E evento `contract_proposal` criado para caminhao terceiro idle
15. `test_confirm_order_no_truck_available` — nenhum caminhao idle → `mock_warehouse_service.confirm_order` chamado, nenhum evento criado, sem excecao
6. `test_reject_order_calls_warehouse_service` — chama com `("warehouse", "wh_01", "reject_order", {"order_id": "order_007", "reason": "insuficiente", "retry_after_ticks": 5}, tick=5)` — `mock_warehouse_service.reject_order` chamado
7. `test_request_resupply_creates_order_to_factory` — chama com `("warehouse", "wh_01", "request_resupply", {"material_id": "cimento", "quantity_tons": 80, "from_factory_id": "factory_01"}, tick=5)` — `mock_order_repo.create` chamado com `target_type="factory"`, `target_id="factory_01"`
8. `test_request_resupply_deduplicates` — `mock_order_repo.has_active_order` retorna `True` — `mock_order_repo.create` nao chamado
9. `test_start_production_updates_factory` — chama com `("factory", "factory_01", "start_production", {"material_id": "cimento", "quantity_tons": 100}, tick=5)` — `mock_factory_repo.update_production_rate` chamado
10. `test_send_stock_creates_order_and_event` — chama com `("factory", "factory_01", "send_stock", {"material_id": "cimento", "quantity_tons": 50, "destination_warehouse_id": "wh_01"}, tick=5)` — `mock_order_repo.create` chamado com `requester_type="factory"` + evento criado para caminhao
11. `test_accept_contract_assigns_route` — chama com `("truck", "truck_01", "accept_contract", {"order_id": "order_007", "chosen_route_risk_level": "low"}, tick=5)` com mock de `TruckRepository.get_by_id` retornando truck com posicao e `OrderRepository.get_by_id` retornando order com origin/dest — `mock_route_service.compute_route` e `mock_route_service.create_route` e `mock_truck_service.assign_route` chamados
12. `test_request_maintenance_schedules` — chama com `("truck", "truck_01", "request_maintenance", {"current_degradation": 0.96}, tick=5)` — `mock_truck_service.schedule_maintenance` chamado com `"truck_01"`
13. `test_refuse_contract_publishes_event` — chama com `("truck", "truck_01", "refuse_contract", {"order_id": "order_007", "reason": "high_degradation"}, tick=5)` — verifica que um novo evento e publicado para re-avaliar outro caminhao
14. `test_effect_failure_does_not_raise` — `mock_warehouse_service.confirm_order` levanta `Exception` — `processor.process()` nao levanta, retorna normalmente (erro e logado)

**PARAR apos criar os testes. Nao escrever nenhum codigo de implementacao. Aguardar aprovacao do usuario.**

---

### Grupo 2 — DecisionEffectProcessor (FASE 2)

**Tarefa:** Implementar o service principal.

1. Criar `backend/src/services/decision_effect_processor.py`:
   - Classe `DecisionEffectProcessor` com construtor que recebe os services/repos necessarios
   - Metodo `async process(entity_type, entity_id, action, payload, current_tick)`:
     - Se `action == "hold"`: return imediatamente
     - Lookup no registry interno `_HANDLERS: dict[tuple[str, str], Callable]` mapeando `(entity_type, action)` -> metodo handler
     - Se nao encontrar handler: log warning e return
     - Try/except no handler: se falhar, log error mas nao raise
   - Handlers privados: `_handle_order_replenishment`, `_handle_confirm_order`, `_handle_reject_order`, `_handle_request_resupply`, `_handle_start_production`, `_handle_send_stock`, `_handle_accept_contract`, `_handle_refuse_contract`, `_handle_request_maintenance`

2. Implementar `OrderRepository.has_active_order(requester_id, material_id, target_id=None) -> bool`:
   - Query: `SELECT 1 FROM pending_orders WHERE requester_id=? AND material_id=? AND status IN ('pending', 'confirmed') [AND target_id=?] LIMIT 1`

---

### Grupo 3 — Handlers de Store e Warehouse (FASE 2)

**Tarefa:** Implementar os handlers para decisoes de loja e armazem.

1. `_handle_order_replenishment(entity_id, payload, tick)`:
   - Chama `has_active_order(entity_id, payload["material_id"], payload["from_warehouse_id"])`
   - Se ja existe: log skip, return
   - Senao: `OrderRepository.create({requester_type: "store", requester_id: entity_id, target_type: "warehouse", target_id: payload["from_warehouse_id"], material_id: payload["material_id"], quantity_tons: payload["quantity_tons"], status: "pending"})`

2. `_handle_confirm_order(entity_id, payload, tick)`:
   - Chama `WarehouseService.confirm_order(payload["order_id"], payload["eta_ticks"])`
   - Despacha caminhao para entrega warehouse→store:
     - Busca caminhao terceiro `idle` mais proximo do armazem via `TruckRepository` (armazens nao tem proprietarios — `factory_id` e vinculo exclusivo de fabricas)
     - Se encontrar: cria evento `contract_proposal` via `EventRepository.create()` com `entity_type="truck"`, `entity_id=truck.id`, `event_type="contract_proposal"`, payload com `order_id`, origin (warehouse), destination (store/requester)
     - Se nao encontrar: loga warning, ordem fica `confirmed` aguardando caminhao disponivel

3. `_handle_reject_order(entity_id, payload, tick)`:
   - Chama `WarehouseService.reject_order(payload["order_id"], payload["reason"])`

4. `_handle_request_resupply(entity_id, payload, tick)`:
   - Deduplicacao: `has_active_order(entity_id, payload["material_id"], payload["from_factory_id"])`
   - Se nao existe: cria PendingOrder com `requester_type: "warehouse"`, `target_type: "factory"`, `target_id: payload["from_factory_id"]`

---

### Grupo 4 — Handlers de Factory e Truck (FASE 2)

**Tarefa:** Implementar os handlers para decisoes de fabrica e caminhao.

1. `_handle_start_production(entity_id, payload, tick)`:
   - Chama `FactoryRepository.update_production_rate(entity_id, payload["material_id"], payload["quantity_tons"])`

2. `_handle_send_stock(entity_id, payload, tick)`:
   - Deduplicacao: `has_active_order(entity_id, payload["material_id"], payload["destination_warehouse_id"])`
   - Se nao existe: cria PendingOrder com `requester_type: "factory"`, `target_type: "warehouse"`
   - Busca caminhao disponivel: proprietario da fabrica (idle) > terceiro (idle) mais proximo
   - Se encontrou: cria evento `new_order` (proprietario) ou `contract_proposal` (terceiro) via EventRepository

3. `_handle_accept_contract(entity_id, payload, tick)`:
   - Busca o caminhao via `TruckRepository.get_by_id(entity_id)`
   - Busca a ordem via `OrderRepository.get_by_id(payload["order_id"])`
   - Resolve coordenadas de origem e destino (lookup da entidade origin/dest)
   - Chama `RouteService.compute_route(from_lat, from_lng, to_lat, to_lng, tick)`
   - Chama `RouteService.create_route(truck_id, origin_type, origin_id, dest_type, dest_id, route_data)`
   - Chama `TruckService.assign_route(truck_id, route.id, cargo)`

4. `_handle_refuse_contract(entity_id, payload, tick)`:
   - Publica evento para re-avaliar outro caminhao disponivel
   - Busca proximo caminhao idle e cria novo evento `contract_proposal`

5. `_handle_request_maintenance(entity_id, payload, tick)`:
   - Chama `TruckService.schedule_maintenance(entity_id)`

---

### Grupo 5 — Integracao com o Grafo LangGraph (FASE 2)

**Tarefa:** Conectar o processor ao nó `act` do grafo.

1. Modificar `build_agent_graph()` em `backend/src/agents/base.py`:
   - Adicionar parametro `decision_effect_processor` (pode ser `None` para backwards-compat)
   - Passar o processor para `_make_act_node_for_graph()`

2. Modificar `_make_act_node_for_graph()` em `backend/src/agents/base.py`:
   - Apos `await repo.create(...)` e antes de `await publish_agent_decision(...)`:
   ```python
   if decision_effect_processor is not None:
       await decision_effect_processor.process(
           entity_type, state["entity_id"],
           raw.get("action"), raw.get("payload", {}),
           state["current_tick"],
       )
   ```

3. Atualizar cada agente concreto (`store_agent.py`, `warehouse_agent.py`, `factory_agent.py`, `truck_agent.py`):
   - Instanciar `DecisionEffectProcessor` com os repos/services necessarios
   - Passar para `build_agent_graph(..., decision_effect_processor=processor)`

---

### Grupo 6 — Validacao e Finalizacao (sequencial, apos Grupos 2-5)

**Tarefa:** Rodar testes e atualizar state.

1. Rodar os testes: `pytest backend/tests/unit/services/test_decision_effect_processor.py -v`
   - Corrigir qualquer falha antes de avancar
   - Todos os testes devem passar com `PASSED`

2. Rodar testes existentes para garantir nao-regressao:
   - `pytest backend/tests/unit/agents/ -v`
   - `pytest backend/tests/integration/ -v` (se banco disponivel)

3. Atualizar `state.md`: adicionar feature 24 na tabela com status adequado.

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos.
Todos os testes em `backend/tests/unit/services/test_decision_effect_processor.py` passam.
Testes existentes de agentes continuam passando (nao-regressao).
`state.md` atualizado com feature 24 como `done`.
