# Tasks — Feature 26: Delivery Completion

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — arquitetura MAS (§4.2), simulacao e caos (§4.4), fisica deterministica (§4.1), fluxo de decisao (§7), TDD (§9), convencoes (§8)
- `.specs/features/26_delivery_completion/specs.md` — criterios de aceitacao desta feature
- `backend/src/simulation/engine.py` — `SimulationEngine._apply_physics()` linhas 90-178 (bloco de chegada quando `new_eta == 0`: linhas 120-127) e `_evaluate_triggers()` linhas 212-301
- `backend/src/simulation/events.py` — constantes de eventos, `SimulationEvent`, `route_event()`, `trigger_event()`
- `backend/src/database/models/route.py` — schema do `Route` (verificar que `order_id` nao existe ainda)
- `backend/src/database/models/truck.py` — `Truck.cargo` e JSONB com `{"material_id": ..., "quantity_tons": ...}`
- `backend/src/database/models/order.py` — schema do `PendingOrder`
- `backend/src/repositories/order.py` — `OrderRepository.update_status()`
- `backend/src/repositories/warehouse.py` — `WarehouseRepository.update_stock(warehouse_id, material_id, delta)`
- `backend/src/repositories/store.py` — `StoreRepository.update_stock(store_id, material_id, delta)`
- `backend/src/repositories/route.py` — `RouteRepository.get_active_by_truck()`, `update_status()`
- `backend/src/repositories/event.py` — `EventRepository.create()`, `get_active_for_entity()`
- `backend/src/repositories/truck.py` — `TruckRepository.set_cargo()`, `update_status()`, `set_active_route()`
- `backend/src/services/decision_effect_processor.py` — `_handle_accept_contract()` para entender como rotas sao criadas (onde adicionar `order_id`)

Nao leia specs de outras features (exceto Feature 25 specs.md para contexto de `triggered_at_tick` e `ORDER_RECEIVED`/`RESUPPLY_REQUESTED` se necessario). Nao modifique prompts nem guardrails.

---

## Plano de Execucao

**Fase 1 (TDD) — Grupo 1:** escrever todos os testes antes de qualquer implementacao. Parar e aguardar aprovacao.

**Fase 2 (Implementacao) — Grupos 2-6** apos aprovacao dos testes.

---

### Grupo 1 — Testes (FASE 1: TDD) PARAR AQUI

**Tarefa:** Escrever todos os testes unitarios. Nao escrever nenhum codigo de implementacao.

**Estrutura de pastas dos testes:**

```
backend/tests/unit/simulation/
├── __init__.py
├── test_engine_delivery.py           # testes do bloco de chegada em _apply_physics

backend/tests/unit/repositories/
├── __init__.py                       # ja existente (Feature 25)
├── test_route_repository.py          # teste do model Route com order_id
```

Criar `__init__.py` em todos os subdiretorios se nao existirem.

**Fixtures compartilhadas** para `test_engine_delivery.py`:

- `mock_session_factory` — async context manager que retorna `mock_session`
- `mock_session` — `AsyncMock` de `AsyncSession` com `commit` como coroutine
- `mock_publisher_redis` — `AsyncMock`
- `engine` — `SimulationEngine(mock_publisher_redis, mock_session_factory)` com `_tick` setado manualmente para o teste

**Mock helpers** (funcoes ou fixtures que criam mocks reutilizaveis):

- `make_truck(id, status, cargo, active_route_id, current_lat, current_lng, degradation, capacity_tons)` — retorna `MagicMock` de truck entity (do WorldState, nao ORM)
- `make_route(id, truck_id, origin_type, origin_id, dest_type, dest_id, eta_ticks, path, timestamps, status, order_id)` — retorna `MagicMock` de Route ORM model
- `make_order(id, requester_type, requester_id, target_type, target_id, material_id, quantity_tons, status)` — retorna `MagicMock` de PendingOrder ORM model

**Estrategia de patching:** Os testes devem patchear os repositories instanciados dentro de `_apply_physics`. A funcao cria `TruckRepository(session)`, `StoreRepository(session)`, etc. Usar `unittest.mock.patch` nos construtores dos repos para injetar mocks, OU patchear `session.execute` para controlar retornos.

**Alternativa recomendada:** Extrair a logica de chegada em um metodo privado `_handle_truck_arrival(truck, route, session, tick)` para facilitar o teste. Isso nao muda a interface publica — so organiza o codigo. Se essa refatoracao for feita, os testes podem chamar `_handle_truck_arrival` diretamente com mocks.

**Testes em `test_engine_delivery.py`:**

1. `test_arrival_transfers_stock_to_warehouse` — caminhao em transito com `cargo={"material_id": "cimento", "quantity_tons": 50}`, rota com `dest_type="warehouse"`, `dest_id="wh_01"`, `eta_ticks=1` (sera decrementado para 0). Patcha repos. Verifica que `WarehouseRepository.update_stock("wh_01", "cimento", 50)` foi chamado com delta positivo.

2. `test_arrival_transfers_stock_to_store` — mesmo cenario mas `dest_type="store"`, `dest_id="store_01"`. Verifica `StoreRepository.update_stock("store_01", "cimento", 30)` chamado.

3. `test_arrival_empty_cargo_skips_transfer` — caminhao com `cargo=None`, rota com `dest_type="warehouse"`. Verifica que `WarehouseRepository.update_stock` NAO foi chamado.

4. `test_arrival_marks_order_delivered` — rota com `order_id=uuid4()`. Verifica que `OrderRepository.update_status(order_id, "delivered")` foi chamado.

5. `test_arrival_no_order_skips_completion` — rota com `order_id=None`. Verifica que `OrderRepository.update_status` NAO foi chamado.

6. `test_arrival_creates_resupply_delivered_event_for_warehouse` — rota com `dest_type="warehouse"`. Verifica que `EventRepository.create` foi chamado com dict contendo `event_type="resupply_delivered"`, `entity_type="warehouse"`, `entity_id="wh_01"`, `source="engine"`, `status="active"`.

7. `test_arrival_creates_resupply_delivered_event_for_store` — rota com `dest_type="store"`. Verifica que `EventRepository.create` foi chamado com `entity_type="store"`, `entity_id="store_01"`.

8. `test_arrival_creates_truck_arrived_event` — qualquer chegada. Verifica que `EventRepository.create` foi chamado com `event_type="truck_arrived"`, `entity_type="truck"`, `entity_id=truck.id`.

9. `test_arrival_clears_truck_state` — apos chegada, verifica sequencia: `truck_repo.set_cargo(truck.id, None)`, `truck_repo.update_status(truck.id, "idle")`, `truck_repo.set_active_route(truck.id, None)`, `route_repo.update_status(route.id, "completed")` todos chamados.

10. `test_arrival_reads_cargo_before_clearing` — verifica que `material_id` e `quantity_tons` sao lidos do cargo ANTES de `set_cargo(None)`. Isso pode ser verificado checando a ordem das chamadas nos mocks (`call_args_list`).

11. `test_arrival_event_payload_contains_delivery_data` — verifica que o payload do evento `resupply_delivered` contem `material_id`, `quantity_tons`, `from_truck_id`. Verifica que o payload do evento `truck_arrived` contem `route_id`, `dest_type`, `dest_id`.

12. `test_arrival_unknown_dest_type_logs_warning` — rota com `dest_type="factory"`. Verifica que `WarehouseRepository.update_stock` e `StoreRepository.update_stock` NAO sao chamados (log warning esperado, mas stock transfer pulado).

**Testes em `test_route_repository.py`:**

1. `test_route_create_with_order_id` — cria Route com `order_id=uuid4()` no dict de dados. Verifica que `session.add` e chamado com Route contendo `order_id` correto.

2. `test_route_create_without_order_id` — cria Route sem `order_id` no dict. Verifica que o Route e criado com `order_id=None`.

**PARAR apos criar os testes. Nao escrever nenhum codigo de implementacao. Aguardar aprovacao do usuario.**

---

### Grupo 2 — Model Route + Migration (FASE 2)

**Tarefa:** Adicionar `order_id` ao model `Route`.

1. Editar `backend/src/database/models/route.py`:
   - Adicionar import: `from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP` (garantir que `ForeignKey` e `UUID` estao importados)
   - Adicionar coluna: `order_id = Column(UUID(as_uuid=True), ForeignKey("pending_orders.id"), nullable=True)`

2. Gerar migration com Alembic:
   - `alembic revision --autogenerate -m "add order_id to routes"`
   - Verificar que a migration so contem `add_column` para `order_id`
   - Rodar: `alembic upgrade head`

---

### Grupo 3 — Events Constants (FASE 2)

**Tarefa:** Adicionar constantes faltantes em `events.py`.

1. Editar `backend/src/simulation/events.py`:
   - Verificar se `RESUPPLY_DELIVERED` ja foi adicionada pela Feature 25. Se nao:
     ```python
     RESUPPLY_DELIVERED = "resupply_delivered"
     ```
   - `TRUCK_ARRIVED` ja existe — confirmar.

---

### Grupo 4 — Engine: Bloco de Chegada (FASE 2)

**Tarefa:** Implementar as 4 acoes de delivery completion em `_apply_physics()`.

1. Editar `backend/src/simulation/engine.py`:

   - Adicionar imports no topo:
     ```python
     from src.repositories.event import EventRepository
     ```
     (Verificar se ja existe — `EventRepository` e usado em `_evaluate_triggers`.)

   - No metodo `_apply_physics()`, adicionar `event_repo = EventRepository(session)` na inicializacao dos repos.

   - Substituir o bloco `if new_eta == 0:` (linhas ~120-127) pelo seguinte:

     ```python
     if new_eta == 0:
         # 1. Stock transfer — read cargo before clearing
         cargo = truck.cargo
         if cargo and isinstance(cargo, dict):
             material_id = cargo.get("material_id")
             quantity_tons = cargo.get("quantity_tons", 0.0)
             if material_id and quantity_tons > 0:
                 if route.dest_type == "warehouse":
                     await warehouse_repo.update_stock(
                         route.dest_id, material_id, quantity_tons
                     )
                 elif route.dest_type == "store":
                     await store_repo.update_stock(
                         route.dest_id, material_id, quantity_tons
                     )
                 else:
                     logger.warning(
                         "Truck {} arrived at unsupported dest_type '{}', skipping stock transfer",
                         truck.id, route.dest_type,
                     )

         # 2. Order completion
         if route.order_id is not None:
             await order_repo.update_status(route.order_id, "delivered")

         # 3. Destination event (resupply_delivered)
         if route.dest_type in ("warehouse", "store"):
             delivery_payload = {}
             if cargo and isinstance(cargo, dict):
                 delivery_payload = {
                     "material_id": cargo.get("material_id"),
                     "quantity_tons": cargo.get("quantity_tons"),
                     "from_truck_id": truck.id,
                 }
             await event_repo.create({
                 "event_type": "resupply_delivered",
                 "entity_type": route.dest_type,
                 "entity_id": route.dest_id,
                 "source": "engine",
                 "status": "active",
                 "tick_start": self._tick,
                 "payload": delivery_payload,
             })

         # 4. Truck event (truck_arrived)
         await event_repo.create({
             "event_type": "truck_arrived",
             "entity_type": "truck",
             "entity_id": truck.id,
             "source": "engine",
             "status": "active",
             "tick_start": self._tick,
             "payload": {
                 "route_id": str(route.id),
                 "dest_type": route.dest_type,
                 "dest_id": route.dest_id,
             },
         })

         # 5. Finalize truck state
         if route.path and route.timestamps:
             final_lng, final_lat = route.path[-1]
             await truck_repo.update_position(truck.id, final_lat, final_lng)
         await truck_repo.set_cargo(truck.id, None)
         await truck_repo.update_status(truck.id, "idle")
         await truck_repo.set_active_route(truck.id, None)
         await route_repo.update_status(route.id, "completed")
     ```

   - Verificar que `WarehouseRepository` e inicializado no metodo. Atualmente `_apply_physics` cria `truck_repo`, `store_repo`, `factory_repo`, `order_repo`, `route_repo`. Adicionar:
     ```python
     warehouse_repo = WarehouseRepository(session)
     ```
     (Verificar se ja existe — pode ja estar importado mas nao instanciado neste metodo.)

---

### Grupo 5 — Engine: Triggers para Warehouse/Store Events (FASE 2)

**Tarefa:** Garantir que `_evaluate_triggers()` desperta agentes de warehouse e store quando ha eventos `resupply_delivered` ativos.

1. Editar `backend/src/simulation/engine.py`, metodo `_evaluate_triggers()`:

   - Atualmente, busca eventos ativos apenas para trucks. Adicionar busca para warehouses e stores:

     ```python
     # Event-based triggers for warehouses
     for warehouse in world_state.warehouses:
         active_events = await event_repo.get_active_for_entity(
             "warehouse", warehouse.id
         )
         for evt in active_events:
             triggers.append(
                 (
                     self._make_agent_callable("warehouse", warehouse.id),
                     trigger_event(
                         "warehouse",
                         warehouse.id,
                         evt.event_type,
                         self._tick,
                         payload=evt.payload or {},
                     ),
                 )
             )
             await event_repo.resolve(evt.id, self._tick)

     # Event-based triggers for stores
     for store in world_state.stores:
         active_events = await event_repo.get_active_for_entity(
             "store", store.id
         )
         for evt in active_events:
             triggers.append(
                 (
                     self._make_agent_callable("store", store.id),
                     trigger_event(
                         "store",
                         store.id,
                         evt.event_type,
                         self._tick,
                         payload=evt.payload or {},
                     ),
                 )
             )
             await event_repo.resolve(evt.id, self._tick)
     ```

   - Nota: o engine resolve o evento imediatamente apos criar o trigger. O payload completo ja esta no `SimulationEvent` que o agente recebe — o agente nao precisa re-consultar o `ChaosEvent`.

   - Para trucks, o codigo atual ja busca eventos ativos e cria triggers. Verificar se ele tambem resolve os eventos apos criar o trigger. Se nao, adicionar `await event_repo.resolve(evt.id, self._tick)` apos cada trigger de truck tambem (consistencia).

   - Adicionar `await session.commit()` no final do bloco `async with` se nao existir (para persistir as resolucoes de eventos).

---

### Grupo 6 — Integracao com Feature 24 (FASE 2)

**Tarefa:** Ajustar `DecisionEffectProcessor._handle_accept_contract()` para passar `order_id` na criacao da rota.

1. Editar `backend/src/services/decision_effect_processor.py`:

   - No handler `_handle_accept_contract`, ao chamar `RouteService.create_route()` (ou `RouteRepository.create()`), incluir `order_id` no dict de dados:
     ```python
     route_data["order_id"] = payload.get("order_id")
     ```

   - Verificar que `RouteService.create_route()` repassa o `order_id` para `RouteRepository.create()` sem filtra-lo.

---

### Grupo 7 — Verificacao do ChaosEvent model (FASE 2)

**Tarefa:** Verificar que o model `ChaosEvent` suporta os campos usados na criacao de eventos.

1. Ler `backend/src/database/models/event.py`:
   - Verificar que `ChaosEvent` tem `payload` (JSONB), `tick_start` (Integer), `source` (String), `status` (String), `entity_type` (String), `entity_id` (String)
   - Se `payload` nao existir como coluna, adiciona-la
   - Se `tick_start` nao existir, verificar o campo correto para o tick de criacao

---

### Grupo 8 — Validacao e Finalizacao (sequencial, apos Grupos 2-7)

**Tarefa:** Rodar testes e atualizar state.

1. Rodar os testes novos:
   - `pytest backend/tests/unit/simulation/test_engine_delivery.py -v`
   - `pytest backend/tests/unit/repositories/test_route_repository.py -v`
   - Corrigir qualquer falha antes de avancar

2. Rodar testes existentes para garantir nao-regressao:
   - `pytest backend/tests/unit/simulation/ -v`
   - `pytest backend/tests/unit/agents/ -v`
   - `pytest backend/tests/unit/services/ -v`
   - `pytest backend/tests/integration/ -v` (se banco disponivel)

3. Verificar end-to-end manual (se possivel):
   - Criar PendingOrder, despachar caminhao, aguardar ticks ate ETA=0
   - Confirmar que estoque do destino aumentou
   - Confirmar que a PendingOrder esta com status `delivered`
   - Confirmar que eventos `resupply_delivered` e `truck_arrived` foram criados e processados

4. Atualizar `state.md`: adicionar feature 26 na tabela com status adequado.

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos.
Todos os testes novos passam com `pytest`.
Testes existentes de engine, agents e services continuam passando (nao-regressao).
O ciclo completo funciona: ordem criada -> caminhao despachado -> caminhao chega -> estoque atualizado -> ordem delivered -> agentes notificados.
`state.md` atualizado com feature 26 como `done`.
