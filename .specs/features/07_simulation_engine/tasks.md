# Tasks — Feature 07: Simulation Engine

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — arquitetura do engine (§4.4 Simulação & Caos), Redis Pub/Sub (§4.5), convenções (§8), TDD (§9), estrutura de pastas (§3)
- `.specs/features/07_simulation_engine/specs.md` — critérios de aceitação
- `.specs/design.md §1` — schemas de `trucks`, `factory_products`, `warehouse_stocks`, `store_stocks`, `pending_orders`, `events`
- `.specs/prd.md §2` — definição de tick, separação física vs. agente, gatilhos preditivos

Não leia specs de outras features. Esta feature pressupõe que os serviços das features 04–06 existem e estão funcionais.

---

## Plano de Execução

O **Grupo 1** (testes) roda primeiro e é obrigatório — aguardar aprovação do usuário antes de avançar.

Os **Grupos 2A e 2B** rodam em paralelo após aprovação dos testes — são independentes entre si.

O **Grupo 3** roda após a conclusão dos Grupos 2A e 2B — `engine.py` e `chaos.py` dependem dos tipos definidos em `events.py` (Grupo 2A).

---

### Grupo 1 — Testes (um agente) ⚠ PARAR AQUI

**Tarefa:** Escrever todos os testes unitários da feature. Não implementar código de produção.

Criar `backend/tests/unit/simulation/test_engine.py`:

1. `test_apply_physics_advances_truck_position` — dado um truck `in_transit` com `path` de 2 waypoints e `timestamps` no futuro, após 1 tick a `current_lat`/`current_lng` deve ser interpolada para a posição correta com base no tempo
2. `test_apply_physics_marks_truck_arrived_when_route_complete` — truck que esgota seu `eta_ticks` é marcado como `idle`, `cargo` zerado, `active_route_id` nulo
3. `test_apply_physics_decrements_store_stock_by_demand_rate` — `StoreStock.stock` reduz exatamente `demand_rate` por tick; não vai abaixo de `0.0`
4. `test_apply_physics_increments_factory_stock_by_production_rate` — `FactoryProduct.stock` aumenta por `production_rate_current`; não ultrapassa `stock_max`
5. `test_apply_physics_zeros_production_when_stock_max_reached` — quando `stock == stock_max`, `production_rate_current` é zerado
6. `test_apply_physics_increments_truck_degradation` — degradação cresce proporcionalmente a distância × `cargo.quantity` para trucks `in_transit`
7. `test_apply_physics_blocks_trip_when_degradation_above_95_pct` — truck com `degradation >= 0.95` tem viagem bloqueada; `status` permanece `idle`
8. `test_apply_physics_increments_pending_order_age` — todos os `PendingOrder` com `status in (pending, confirmed)` têm `age_ticks += 1`
9. `test_evaluate_triggers_wakes_store_when_projected_stockout` — dado `stock=5.0`, `reorder_point=4.0`, `demand_rate=1.0`, `lead_time_ticks=3`: `(5.0 - 4.0) / 1.0 = 1.0 < 3 × 1.5 = 4.5` → gatilho ativo
10. `test_evaluate_triggers_does_not_wake_store_when_stock_ok` — dado `stock=20.0`, `reorder_point=4.0`, `demand_rate=1.0`, `lead_time_ticks=3`: `16.0 / 1.0 = 16 > 4.5` → nenhum gatilho
11. `test_evaluate_triggers_wakes_truck_on_pending_event` — truck com evento `route_blocked` pendente retorna na lista de agentes a acordar
12. `test_evaluate_triggers_does_not_wake_truck_in_transit_without_event` — truck `in_transit` sem eventos pendentes não acorda
13. `test_tick_does_not_block_on_agent_tasks` — verificar que `run_tick()` usa `asyncio.create_task()` (não `await`) ao despachar agentes; mock dos agentes deve confirmar que `create_task` foi chamado e o tick retornou antes da task completar
14. `test_semaphore_limits_agent_concurrency` — semaphore com `MAX_AGENT_WORKERS=1` garante que apenas 1 agente por vez adquire o lock

Criar `backend/tests/unit/simulation/test_publisher.py`:

15. `test_publish_world_state_writes_to_correct_channel` — mock do cliente Redis; verificar que `publish` foi chamado com canal `nexus:world_state` e payload JSON válido
16. `test_publish_agent_decision_writes_to_correct_channel` — canal `nexus:agent_decisions`
17. `test_publish_event_writes_to_correct_channel` — canal `nexus:events`
18. `test_publisher_does_not_raise_on_redis_connection_error` — quando Redis lança `ConnectionError`, o publisher loga via Loguru e não propaga a exceção

Criar `backend/tests/unit/simulation/test_chaos.py`:

19. `test_inject_chaos_event_persists_event_with_active_status` — `inject_chaos_event(...)` persiste `ChaosEvent` com `status=active` no banco (usar session in-memory / mock de repository)
20. `test_manual_only_events_rejected_when_source_is_master_agent` — `event_type=strike` com `source=master_agent` retorna erro sem persistir
21. `test_manual_only_events_rejected_for_route_blocked` — mesmo para `route_blocked`, `storm`, `sudden_demand_zero`
22. `test_can_inject_autonomous_blocked_when_active_event_exists` — `can_inject_autonomous_event()` retorna `False` quando existe evento autônomo `active`
23. `test_can_inject_autonomous_blocked_during_cooldown` — retorna `False` quando último evento autônomo foi resolvido há menos de 24 ticks
24. `test_can_inject_autonomous_allowed_after_cooldown` — retorna `True` quando nenhum evento ativo e cooldown expirou
25. `test_resolve_chaos_event_sets_resolved_status` — `resolve_chaos_event(event_id, tick)` atualiza `status=resolved` e `tick_end`

Criar `backend/tests/unit/simulation/test_events.py`:

26. `test_simulation_event_factory_functions_produce_correct_fields` — `route_event()`, `trigger_event()`, `chaos_event()` produzem `SimulationEvent` com campos corretos

---

**⚠ PARAR AQUI. Não implementar código de produção. Aguardar aprovação do usuário antes de avançar para os grupos seguintes.**

---

### Grupo 2A — Eventos e Publisher (um agente)

Executar em paralelo com Grupo 2B após aprovação dos testes.

**Tarefa:** Implementar os tipos de evento e o publisher Redis.

1. Criar `backend/src/simulation/events.py`:
   - Constantes de tipo de evento como `str` em um namespace ou `StrEnum`: `ROUTE_BLOCKED = "route_blocked"`, `TRUCK_ARRIVED = "truck_arrived"`, `TRUCK_BREAKDOWN = "truck_breakdown"`, `NEW_ORDER = "new_order"`, `CONTRACT_PROPOSAL = "contract_proposal"`, `MACHINE_BREAKDOWN = "machine_breakdown"`, `DEMAND_SPIKE = "demand_spike"`, `STRIKE = "strike"`, `STORM = "storm"`, `SUDDEN_DEMAND_ZERO = "sudden_demand_zero"`, `ENGINE_BLOCKED_DEGRADED_TRUCK = "engine_blocked_degraded_truck"`, `LOW_STOCK_TRIGGER = "low_stock_trigger"`, `STOCK_TRIGGER_WAREHOUSE = "stock_trigger_warehouse"`, `STOCK_TRIGGER_FACTORY = "stock_trigger_factory"`
   - Dataclass `SimulationEvent` com campos: `event_type: str`, `source: str`, `entity_type: str | None`, `entity_id: str | None`, `payload: dict`, `tick: int`
   - Funções de fábrica: `route_event(event_type, entity_id, payload, tick) -> SimulationEvent`, `trigger_event(entity_type, entity_id, event_type, tick) -> SimulationEvent`, `chaos_event(event_type, source, entity_type, entity_id, payload, tick) -> SimulationEvent`

2. Criar `backend/src/simulation/publisher.py`:
   - Função `publish_world_state(world_state: WorldState, tick: int, redis_client)` — serializa `WorldState` para JSON e publica em `nexus:world_state`
   - Função `publish_agent_decision(decision: dict, tick: int, redis_client)` — publica em `nexus:agent_decisions`
   - Função `publish_event(event: SimulationEvent, redis_client)` — publica em `nexus:events`
   - Todas as funções capturam `Exception` no publish, logam via `logger.error()` do Loguru e retornam silenciosamente — sem re-raise
   - `redis_client` é sempre passado como parâmetro (sem import global de conexão)

---

### Grupo 2B — Chaos (um agente)

Executar em paralelo com Grupo 2A após aprovação dos testes.

**Tarefa:** Implementar a interface de injeção de caos.

Criar `backend/src/simulation/chaos.py`:

1. Constante `MANUAL_ONLY_EVENTS: frozenset[str]` com os tipos: `strike`, `route_blocked`, `storm`, `sudden_demand_zero`

2. Função `async inject_chaos_event(event_type: str, payload: dict, source: str, entity_type: str | None, entity_id: str | None, tick: int, session: AsyncSession, redis_client) -> ChaosEvent`:
   - Se `event_type in MANUAL_ONLY_EVENTS` e `source == "master_agent"` → raise `ValueError` com mensagem descritiva
   - Cria e persiste `ChaosEvent` via `EventRepository` com `status="active"`, `tick_start=tick`
   - Publica o evento via `publisher.publish_event()`
   - Retorna o `ChaosEvent` persistido

3. Função `async resolve_chaos_event(event_id: str, tick: int, session: AsyncSession) -> ChaosEvent`:
   - Busca o evento; se não encontrado → raise `ValueError`
   - Atualiza `status="resolved"` e `tick_end=tick`
   - Persiste via `EventRepository`
   - Retorna o `ChaosEvent` atualizado

4. Função `async can_inject_autonomous_event(current_tick: int, session: AsyncSession) -> bool`:
   - Busca eventos autônomos com `status="active"` e `source="master_agent"` via `EventRepository`
   - Se existir algum → retorna `False`
   - Busca o evento autônomo resolvido mais recente
   - Se `current_tick - resolved_event.tick_end < 24` → retorna `False`
   - Caso contrário → retorna `True`

---

### Grupo 3 — Engine (um agente, após Grupos 2A e 2B)

**Tarefa:** Implementar o loop de ticks e a física determinística.

Criar `backend/src/simulation/engine.py`:

1. Classe `SimulationEngine`:
   - `__init__(self, world_state_service: WorldStateService, publisher_redis_client, session_factory)`:
     - `self._running: bool = False`
     - `self._tick: int = 0`
     - `self._tick_interval: float` — lido de `TICK_INTERVAL_SECONDS` (default: `10.0`)
     - `self._semaphore: asyncio.Semaphore` — criado com `MAX_AGENT_WORKERS` do ambiente

2. Método `async start()`:
   - Seta `self._running = True`
   - Entra em loop: `while self._running: await self.run_tick(); await asyncio.sleep(self._tick_interval)`

3. Método `stop()`:
   - Seta `self._running = False`

4. Método `async advance_one_tick()`:
   - Verifica que `self._running is False`; se não → raise `RuntimeError("stop the engine before advancing manually")`
   - Chama `await self.run_tick()`

5. Método `async run_tick()`:
   - Incrementa `self._tick`
   - Carrega `WorldState` via `WorldStateService.load()`
   - Chama `await self._apply_physics(world_state)`
   - Chama `triggers = await self._evaluate_triggers(world_state)`
   - Para cada `(agent_fn, event)` em `triggers`: `asyncio.create_task(self._dispatch_agent(agent_fn, event))`
   - Chama `await publisher.publish_world_state(world_state, self._tick, self._publisher_redis_client)`

6. Método `async _apply_physics(world_state: WorldState)`:
   - Usar `async with session_factory() as session:`
   - Para cada `Truck` com `status="in_transit"`: interpolar posição com base no `path` e `timestamps` da rota ativa vs. o tick atual; se `eta_ticks` chegou a zero → marcar `status="idle"`, zerar `cargo`, `active_route_id=None`; caso contrário → calcular distância percorrida neste tick, incrementar `degradation = degradation + (distance_km × cargo.quantity) / DEGRADATION_FACTOR`, atualizar `breakdown_risk` com fórmula exponencial acima de `0.7`: `max(0.0, (degradation - 0.7) / 0.3) ** 2`
   - Verificar `degradation >= 0.95` antes de qualquer nova viagem: se um truck `idle` foi marcado para partir, bloquear e publicar evento `engine_blocked_degraded_truck`
   - Para cada `StoreStock`: `stock = max(0.0, stock - demand_rate)`
   - Para cada `FactoryProduct`: `stock = min(stock_max, stock + production_rate_current)`; se `stock >= stock_max` → `production_rate_current = 0.0`
   - Para cada `PendingOrder` com `status in ("pending", "confirmed")`: `age_ticks += 1`
   - Persistir todas as alterações via repositories correspondentes

7. Método `async _evaluate_triggers(world_state: WorldState) -> list[tuple]`:
   - Para cada `Store`, para cada produto `p` em `store.stocks`: calcular `lead_time_ticks` como `eta_ticks` estimado do armazém mais próximo (usar posição atual); avaliar `(stock[p] - reorder_point[p]) / demand_rate[p] < lead_time_ticks × 1.5`; se verdadeiro → adicionar `(store_agent.run_cycle, trigger_event("store", store.id, LOW_STOCK_TRIGGER, self._tick))` à lista
   - Para cada `Warehouse`, para cada produto `p`: calcular `demand_rate_estimate` como soma das `demand_rate[p]` das lojas atendidas; avaliar a mesma fórmula com `min_stock[p]`; se verdadeiro → adicionar à lista
   - Para cada `Truck`: buscar eventos pendentes do tipo `route_blocked`, `truck_arrived`, `truck_breakdown`, `new_order`, `contract_proposal` via `EventRepository`; se existir → adicionar à lista
   - Retornar lista de `(agent_fn, event)` — sem chamar agentes aqui

8. Método `async _dispatch_agent(agent_fn, event)`:
   - `async with self._semaphore:`
   - `await agent_fn(event)` (a implementação real dos agentes chega nas features 08–09; por ora, aceitar qualquer callable)

9. Constante `DEGRADATION_FACTOR = 1000.0` — divisor na fórmula de degradação (ajustável para calibração futura)

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes do Grupo 1 passam com `pytest backend/tests/unit/simulation/ -v`.
Atualizar `state.md`: setar o status da feature `07` para `done`.
