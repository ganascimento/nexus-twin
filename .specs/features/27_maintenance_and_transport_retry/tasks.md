# Tasks — Feature 27: Maintenance Completion & Transport Retry

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — arquitetura (§4.1 degradacao, §4.4 tick), TDD (§9), convencoes (§8)
- `.specs/features/27_maintenance_and_transport_retry/specs.md` — criterios de aceitacao desta feature
- `backend/src/simulation/engine.py` — `_apply_physics()` e `_evaluate_triggers()` completos
- `backend/src/services/truck.py` — `schedule_maintenance()` linhas 82-92
- `backend/src/database/models/truck.py` — schema atual do Truck
- `backend/src/database/models/route.py` — schema do Route (precisa de `order_id` de F26)
- `backend/src/repositories/truck.py` — metodos existentes
- `backend/src/repositories/order.py` — metodos existentes
- `backend/src/repositories/route.py` — metodos existentes
- `backend/src/simulation/events.py` — constantes e SimulationEvent
- `backend/src/world/physics.py` — `calculate_maintenance_ticks()`
- `.specs/prd.md` §5 (mecanica de degradacao e tabela de manutencao)

Nao leia specs de outras features. Nao modifique prompts nem guardrails.

---

## Plano de Execucao

**Fase 1 (TDD) — Grupo 1:** escrever todos os testes. Parar e aguardar aprovacao.

**Fase 2 (Implementacao) — Grupos 2-6** apos aprovacao.

---

### Grupo 1 — Testes (FASE 1: TDD) PARAR AQUI

**Tarefa:** Escrever todos os testes. Nao escrever nenhum codigo de implementacao.

**Estrutura de pastas:**

```
backend/tests/unit/simulation/
├── __init__.py
├── test_engine_maintenance.py
├── test_engine_transport_retry.py

backend/tests/unit/services/
├── __init__.py
├── test_truck_service_maintenance.py

backend/tests/unit/repositories/
├── __init__.py
├── test_truck_repository_queries.py
├── test_order_repository_queries.py
```

Criar `__init__.py` em todos os subdiretorios se nao existirem.

**`test_engine_maintenance.py`:**

Fixtures:
- `mock_session_factory` — context manager async retornando `mock_session`
- `mock_session` — `AsyncMock` de `AsyncSession`
- `mock_publisher_redis` — `AsyncMock`
- `engine` — `SimulationEngine(mock_publisher_redis, mock_session_factory)` com `_tick` setado manualmente
- `maintenance_truck` — `MagicMock` com `id="truck_01"`, `status="maintenance"`, `maintenance_start_tick=5`, `maintenance_duration_ticks=8`

Testes:
1. `test_completes_maintenance_after_duration` — `engine._tick=13`, caminhao com `start=5`, `duration=8` → `TruckRepository.update_status("truck_01", "idle")` chamado + `clear_maintenance_info` chamado
2. `test_does_not_complete_maintenance_early` — `engine._tick=10`, mesmos campos → `update_status` nao chamado
3. `test_creates_maintenance_completed_event` — ao completar → `EventRepository.create` chamado com `event_type="truck_maintenance_completed"`, `entity_type="truck"`, `entity_id="truck_01"`
4. `test_handles_legacy_maintenance_without_tracking` — caminhao com `status="maintenance"`, `maintenance_start_tick=None` → `update_status("idle")` chamado imediatamente
5. `test_maintenance_block_runs_before_transit` — verificar que caminhoes em manutencao sao processados antes do loop de IN_TRANSIT (ordem de execucao)

**`test_engine_transport_retry.py`:**

Fixtures:
- Mesmas do maintenance + `mock_order_repo`, `mock_truck_repo`, `mock_event_repo`
- `orphaned_order` — `MagicMock` de PendingOrder com `id=uuid4()`, `status="confirmed"`, `target_type="warehouse"`, `target_id="wh_01"`, `requester_type="store"`, `requester_id="store_01"`, `material_id="cimento"`, `quantity_tons=20`, `age_ticks=5`
- `idle_truck` — `MagicMock` de Truck com `id="truck_04"`, `status="idle"`, `truck_type="terceiro"`, `current_lat=-23.5`, `current_lng=-46.6`

Testes:
1. `test_retries_orphaned_order_with_idle_third_party` — `get_confirmed_without_route` retorna 1 ordem, `get_nearest_idle_third_party` retorna `idle_truck` → `EventRepository.create` chamado com `event_type="contract_proposal"`, `entity_id="truck_04"`, payload com `order_id`
2. `test_retries_factory_order_with_proprietario` — ordem com `target_type="factory"`, `get_idle_by_factory` retorna caminhao → evento `new_order` criado
3. `test_skips_retry_when_no_truck_available` — `get_nearest_idle_third_party` retorna None → nenhum evento criado, sem excecao
4. `test_limits_retry_to_10_per_tick` — `get_confirmed_without_route` retorna 15 ordens → apenas 10 processadas (verificar que o metodo e chamado com `limit=10`)
5. `test_no_duplicate_events_for_same_order` — `get_active_for_entity` retorna evento existente para o caminhao com payload contendo o order_id → nao cria novo evento
6. `test_orders_by_age_ticks_desc` — verifica que ordens mais antigas sao processadas primeiro

**`test_truck_service_maintenance.py`:**

1. `test_schedule_maintenance_saves_tracking_fields` — chama `schedule_maintenance("truck_01")` com mock de truck com `degradation=0.7` → `set_maintenance_info` chamado com `(truck_01, current_tick, duration)` onde duration = `calculate_maintenance_ticks(0.7)`

**`test_truck_repository_queries.py`:**

1. `test_get_idle_by_factory_returns_idle_proprietario` — mock retorna caminhao idle com factory_id correto
2. `test_get_idle_by_factory_returns_none_when_all_busy` — mock retorna None
3. `test_get_nearest_idle_third_party_returns_closest` — mock retorna lista de terceiros idle, verifica que o mais proximo e retornado
4. `test_get_all_in_maintenance_returns_only_maintenance` — mock retorna caminhoes com status maintenance

**`test_order_repository_queries.py`:**

1. `test_get_confirmed_without_route_returns_orphaned` — mock com ordem confirmed sem rota → retornada
2. `test_get_confirmed_without_route_excludes_with_active_route` — mock com ordem confirmed com rota ativa → nao retornada
3. `test_get_confirmed_without_route_orders_by_age_desc` — verifica ordenacao

**PARAR apos criar os testes. Aguardar aprovacao do usuario.**

---

### Grupo 2 — Model e Migration (FASE 2)

1. Editar `backend/src/database/models/truck.py`:
   - Adicionar `maintenance_start_tick = Column(Integer, nullable=True, default=None)`
   - Adicionar `maintenance_duration_ticks = Column(Integer, nullable=True, default=None)`

2. Gerar migration:
   - `alembic revision --autogenerate -m "add maintenance tracking to trucks"`

3. Adicionar constante em `backend/src/simulation/events.py`:
   - `TRUCK_MAINTENANCE_COMPLETED = "truck_maintenance_completed"`

---

### Grupo 3 — Repository (FASE 2)

1. `TruckRepository` — adicionar:
   - `set_maintenance_info(truck_id, start_tick, duration_ticks)`
   - `clear_maintenance_info(truck_id)` — seta ambos para None
   - `get_idle_by_factory(factory_id) -> Truck | None`
   - `get_nearest_idle_third_party(lat, lng) -> Truck | None` — query com ORDER BY distancia euclidiana, LIMIT 1
   - `get_all_in_maintenance() -> list[Truck]`

2. `OrderRepository` — adicionar:
   - `get_confirmed_without_route(limit=10) -> list[PendingOrder]` — LEFT JOIN com routes, WHERE po.status='confirmed' AND r.id IS NULL, ORDER BY age_ticks DESC, LIMIT

---

### Grupo 4 — TruckService (FASE 2)

1. Atualizar `TruckService.schedule_maintenance()`:
   - Apos setar status e zerar degradacao, chamar `self._repo.set_maintenance_info(truck_id, current_tick, duration)`
   - Precisa receber `current_tick` como parametro (adicionar ao metodo)

---

### Grupo 5 — Engine: Maintenance Completion (FASE 2)

1. Em `_apply_physics()`, adicionar bloco ANTES do loop de caminhoes em transito:

   ```python
   for truck in world_state.trucks:
       if truck.status != TruckStatus.MAINTENANCE.value:
           continue
       if truck.maintenance_start_tick is None:
           await truck_repo.update_status(truck.id, "idle")
           await truck_repo.clear_maintenance_info(truck.id)
           logger.warning("Truck {} in maintenance without tracking, forcing idle", truck.id)
           continue
       if self._tick - truck.maintenance_start_tick >= truck.maintenance_duration_ticks:
           await truck_repo.update_status(truck.id, "idle")
           await truck_repo.clear_maintenance_info(truck.id)
           await event_repo.create({
               "event_type": "truck_maintenance_completed",
               "source": "engine",
               "entity_type": "truck",
               "entity_id": truck.id,
               "payload": {},
               "status": "active",
               "tick_start": self._tick,
           })
   ```

2. Precisa de `EventRepository` no bloco de `_apply_physics` — verificar se ja e instanciado, senao adicionar.

---

### Grupo 6 — Engine: Transport Retry Sweep (FASE 2)

1. Em `_evaluate_triggers()`, adicionar bloco apos todos os triggers existentes:

   ```python
   orphaned_orders = await order_repo.get_confirmed_without_route(limit=10)
   for order in orphaned_orders:
       if order.target_type == "factory":
           truck = await truck_repo.get_idle_by_factory(order.target_id)
           event_type = "new_order" if truck else None
       else:
           truck = None
           event_type = None

       if truck is None:
           truck = await truck_repo.get_nearest_idle_third_party(
               # coordenadas da entidade de origem (target)
               # precisa resolver lat/lng do target
           )
           event_type = "contract_proposal" if truck else None

       if truck is None:
           continue

       # verificar se ja existe evento ativo para esta ordem
       existing = await event_repo.get_active_for_entity("truck", truck.id)
       if any(e.payload.get("order_id") == str(order.id) for e in existing):
           continue

       await event_repo.create({
           "event_type": event_type,
           "source": "engine",
           "entity_type": "truck",
           "entity_id": truck.id,
           "payload": {
               "order_id": str(order.id),
               "material_id": order.material_id,
               "quantity_tons": order.quantity_tons,
               "target_type": order.target_type,
               "target_id": order.target_id,
               "requester_type": order.requester_type,
               "requester_id": order.requester_id,
           },
           "status": "active",
           "tick_start": self._tick,
       })
   ```

2. Para resolver lat/lng do target, carregar a entidade do WorldState:
   - Se `target_type == "warehouse"`: buscar warehouse no `world_state.warehouses` por id
   - Se `target_type == "factory"`: buscar factory no `world_state.factories` por id

---

### Grupo 7 — Validacao (sequencial)

1. Rodar testes novos:
   - `pytest backend/tests/unit/simulation/test_engine_maintenance.py -v`
   - `pytest backend/tests/unit/simulation/test_engine_transport_retry.py -v`
   - `pytest backend/tests/unit/services/test_truck_service_maintenance.py -v`
   - `pytest backend/tests/unit/repositories/ -v`

2. Rodar testes existentes (nao-regressao):
   - `pytest backend/tests/unit/simulation/ -v`
   - `pytest backend/tests/unit/agents/ -v`
   - `pytest backend/tests/integration/ -v`

3. Atualizar `state.md`

---

## Condicao de Conclusao

Todos os criterios de aceitacao satisfeitos.
Todos os testes passam.
Caminhoes em manutencao voltam a idle apos duracao.
Ordens confirmadas sem rota sao reavaliadas a cada tick.
`state.md` atualizado.
