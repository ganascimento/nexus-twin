# Tasks — Feature 28: Resilience & Chaos

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — arquitetura (§4.4 caos, §4.2 perfis caminhao), TDD (§9), convencoes (§8)
- `.specs/features/28_resilience_and_chaos/specs.md` — criterios de aceitacao
- `.specs/prd.md` §5 (mecanica de degradacao, backoff de rejeicao), §7 (eventos de caos)
- `backend/src/simulation/engine.py` — `_apply_physics()` e `_evaluate_triggers()` completos
- `backend/src/simulation/events.py` — constantes e SimulationEvent
- `backend/src/world/physics.py` — funcoes existentes: `calculate_breakdown_risk`, `is_trip_blocked`
- `backend/src/guardrails/truck.py` — acoes validas e payloads
- `backend/src/agents/prompts/store.md`, `factory.md`, `truck.md` — triggers atuais
- `backend/src/repositories/order.py`, `event.py`, `truck.py`, `route.py`
- `backend/src/services/chaos.py`, `truck.py`, `route.py`

Nao leia specs de outras features.

---

## Plano de Execucao

**Fase 1 (TDD) — Grupo 1:** escrever todos os testes. Parar e aguardar aprovacao.

**Fase 2 (Implementacao) — Grupos 2-7** apos aprovacao. Grupos 2-5 podem ser paralelos. Grupo 6 (engine) depende de 2-5. Grupo 7 e validacao.

---

### Grupo 1 — Testes (FASE 1: TDD) PARAR AQUI

**Estrutura de pastas:**

```
backend/tests/unit/simulation/
├── test_engine_retry_backoff.py      # Gap A
├── test_engine_breakdown_roll.py     # Gap B
├── test_engine_chaos_triggers.py     # Gap C

backend/tests/unit/repositories/
├── test_order_repository_retry.py    # Gap A
├── test_route_repository_update.py   # Gap D

backend/tests/unit/guardrails/
├── test_truck_guardrail_reroute.py   # Gap D

backend/tests/unit/services/
├── test_decision_effect_reroute.py   # Gap D
├── test_decision_effect_breakdown.py # Gap B
├── test_decision_effect_production.py # Gap C
```

**Gap A — Retry Backoff:**

`test_order_repository_retry.py`:
1. `test_get_retry_eligible_returns_expired_backoff` — ordem rejeitada, `retry_after_tick=6`, `age_ticks=8` → retornada
2. `test_get_retry_eligible_excludes_active_backoff` — `retry_after_tick=6`, `age_ticks=3` → nao retornada
3. `test_get_retry_eligible_excludes_non_rejected` — ordens pending/confirmed → nao retornadas

`test_engine_retry_backoff.py`:
4. `test_fires_retry_eligible_for_store` — loja com ordem elegivel → trigger `order_retry_eligible`
5. `test_no_retry_if_backoff_active` — backoff ativo → sem trigger
6. `test_retry_trigger_includes_order_data` — payload contem `order_id`, `material_id`, `from_warehouse_id`

**Gap B — Breakdown Roll:**

`test_engine_breakdown_roll.py`:
7. `test_breakdown_roll_creates_event` — mock random < breakdown_risk → status `broken`, evento `truck_breakdown` criado, cargo mantido
8. `test_no_breakdown_when_roll_passes` — mock random > breakdown_risk → continua IN_TRANSIT
9. `test_breakdown_skipped_when_risk_zero` — `breakdown_risk=0` → roll nao e chamado

`test_decision_effect_breakdown.py`:
10. `test_alert_breakdown_dispatches_rescue` — handler busca caminhao de resgate + cria evento

**Gap C — Chaos Triggers:**

`test_engine_chaos_triggers.py`:
11. `test_fires_trigger_for_factory_machine_breakdown` — fabrica com evento ativo → trigger com event_type correto
12. `test_fires_trigger_for_store_demand_spike` — loja com evento ativo → trigger disparado
13. `test_resolves_event_after_trigger` — evento marcado `resolved` apos criar trigger
14. `test_does_not_retrigger_resolved` — evento resolvido → sem trigger

`test_decision_effect_production.py`:
15. `test_stop_production_sets_rate_zero` — handler chama `update_production_rate(factory_id, material_id, 0.0)`

**Gap D — Reroute:**

`test_truck_guardrail_reroute.py`:
16. `test_reroute_action_accepted` — `TruckDecision(action="reroute", ...)` nao levanta erro
17. `test_reroute_requires_payload` — reroute sem payload → ValidationError

`test_decision_effect_reroute.py`:
18. `test_handle_reroute_computes_new_route` — chama `RouteService.compute_route` com posicao atual → destino
19. `test_handle_reroute_updates_active_route` — `RouteRepository.update_route_data` chamado

`test_route_repository_update.py`:
20. `test_update_route_data` — atualiza path, timestamps, eta_ticks de rota existente

**PARAR apos criar os testes. Aguardar aprovacao do usuario.**

---

### Grupo 2 — Gap A: Repository + Events (FASE 2)

1. `OrderRepository.get_retry_eligible(requester_id, current_tick)`:
   ```python
   result = await self._session.execute(
       select(PendingOrder).where(
           PendingOrder.requester_id == requester_id,
           PendingOrder.status == "rejected",
           PendingOrder.retry_after_tick.isnot(None),
           PendingOrder.age_ticks >= PendingOrder.retry_after_tick,
       )
   )
   return result.scalars().all()
   ```

2. Adicionar constante `ORDER_RETRY_ELIGIBLE = "order_retry_eligible"` em events.py

3. Atualizar prompt `backend/src/agents/prompts/store.md`:
   - Adicionar secao `## Gatilho: order_retry_eligible`
   - Instrucoes: verificar se o armazem original e viavel, senao tentar outro. Emitir `order_replenishment` com novo ou mesmo `from_warehouse_id`.

---

### Grupo 3 — Gap B: Physics + Guardrail (FASE 2)

1. Adicionar `roll_breakdown(breakdown_risk)` em physics.py:
   ```python
   import random
   def roll_breakdown(breakdown_risk: float) -> bool:
       if breakdown_risk <= 0:
           return False
       return random.random() < breakdown_risk
   ```

2. Adicionar `AlertBreakdownPayload` em guardrails/truck.py:
   ```python
   class AlertBreakdownPayload(BaseModel):
       current_degradation: float
       route_id: str | None = None
   ```

3. Atualizar union de payloads em `TruckDecision.payload` para incluir `AlertBreakdownPayload`

---

### Grupo 4 — Gap C: Nada de repository/model (FASE 2)

Sem alteracoes em models ou repositories. A infraestrutura ja existe. Prosseguir direto para o engine (Grupo 6).

Unica alteracao: DecisionEffectProcessor (F24) precisa de handler para `stop_production`:
- `_handle_stop_production(entity_id, payload, tick)`:
  - Se payload contem `affected_product_id`: `FactoryRepository.update_production_rate(entity_id, affected_product_id, 0.0)`
  - Se nao: para producao de todos os produtos da fabrica

---

### Grupo 5 — Gap D: Guardrail + Repository + Service (FASE 2)

1. Guardrail — editar `backend/src/guardrails/truck.py`:
   - Adicionar `"reroute"` a lista de Literal em `TruckDecision.action`
   - Criar `ReroutePayload(BaseModel)` com `order_id: str`, `reason: str`
   - Incluir na union de payloads

2. Repository — adicionar `RouteRepository.update_route_data(route_id, path, timestamps, eta_ticks)`:
   ```python
   await self._session.execute(
       update(Route)
       .where(Route.id == route_id)
       .values(path=path, timestamps=timestamps, eta_ticks=eta_ticks)
   )
   ```

3. DecisionEffectProcessor handler `_handle_reroute(entity_id, payload, tick)`:
   - Busca caminhao via `TruckRepository.get_by_id(entity_id)`
   - Busca rota ativa via `RouteRepository.get_active_by_truck(entity_id)`
   - Resolve coordenadas do destino (dest_type + dest_id → lat/lng)
   - Chama `RouteService.compute_route(truck.current_lat, truck.current_lng, dest_lat, dest_lng, tick)`
   - Chama `RouteRepository.update_route_data(route.id, new_path, new_timestamps, new_eta)`

---

### Grupo 6 — Engine Integration (FASE 2, depende de 2-5)

#### 6a. Breakdown roll em _apply_physics()

No bloco de caminhoes IN_TRANSIT, apos calcular `new_breakdown_risk`:

```python
from src.world.physics import roll_breakdown

if roll_breakdown(new_breakdown_risk):
    await truck_repo.update_status(truck.id, "broken")
    await event_repo.create({
        "event_type": "truck_breakdown",
        "source": "engine",
        "entity_type": "truck",
        "entity_id": truck.id,
        "payload": {
            "route_id": str(route.id),
            "cargo": truck.cargo,
            "lat": new_lat,
            "lng": new_lng,
        },
        "status": "active",
        "tick_start": self._tick,
    })
    continue  # nao atualiza posicao/degradacao — caminhao parou
```

Adicionar `EventRepository(session)` como `event_repo` no bloco de physics.

#### 6b. Chaos triggers para fabricas e lojas em _evaluate_triggers()

Apos os triggers de estoque/ordens de fabricas:

```python
for factory in world_state.factories:
    active_events = await event_repo.get_active_for_entity("factory", factory.id)
    for event in active_events:
        triggers.append((
            self._make_agent_callable("factory", factory.id),
            trigger_event("factory", factory.id, event.event_type, self._tick,
                         payload={"event_id": str(event.id), **(event.payload or {})}),
        ))
        await event_repo.resolve(event.id, self._tick)
```

Mesmo padrao para lojas:

```python
for store in world_state.stores:
    active_events = await event_repo.get_active_for_entity("store", store.id)
    for event in active_events:
        triggers.append((
            self._make_agent_callable("store", store.id),
            trigger_event("store", store.id, event.event_type, self._tick,
                         payload={"event_id": str(event.id), **(event.payload or {})}),
        ))
        await event_repo.resolve(event.id, self._tick)
```

Resolve evento imediatamente apos criar trigger (payload ja esta no SimulationEvent).

#### 6c. Retry backoff em _evaluate_triggers()

Apos os triggers de estoque das lojas:

```python
for store in world_state.stores:
    retry_eligible = await order_repo.get_retry_eligible(store.id, self._tick)
    if retry_eligible:
        order = retry_eligible[0]  # mais urgente primeiro
        triggers.append((
            self._make_agent_callable("store", store.id),
            trigger_event("store", store.id, ORDER_RETRY_ELIGIBLE, self._tick,
                         payload={
                             "order_id": str(order.id),
                             "material_id": order.material_id,
                             "original_target_id": order.target_id,
                         }),
        ))
```

#### 6d. Route blocked → truck triggers

No bloco de trucks em _evaluate_triggers(), alem de verificar eventos diretos para o caminhao, verificar eventos globais de `route_blocked`:

```python
# buscar eventos route_blocked ativos (nao vinculados a um truck especifico)
blocked_events = await event_repo.get_active_by_type("route_blocked")
for event in blocked_events:
    for truck in world_state.trucks:
        if truck.status != TruckStatus.IN_TRANSIT.value:
            continue
        # simplificacao: qualquer truck IN_TRANSIT e notificado
        # (logica precisa de matching rota x area bloqueada pode vir depois)
        triggers.append((
            self._make_agent_callable("truck", truck.id),
            trigger_event("truck", truck.id, ROUTE_BLOCKED, self._tick,
                         payload=event.payload or {}),
        ))
    await event_repo.resolve(event.id, self._tick)
```

Precisa de `EventRepository.get_active_by_type(event_type) -> list[ChaosEvent]` — novo metodo.

---

### Grupo 7 — Validacao (sequencial)

1. Rodar testes novos: `pytest backend/tests/unit/ -v -k "retry_backoff or breakdown_roll or chaos_triggers or reroute or retry or breakdown or production"`
2. Rodar testes existentes (nao-regressao): `pytest backend/tests/ -v`
3. Atualizar state.md

---

## Condicao de Conclusao

Todos os criterios de aceitacao dos 4 gaps satisfeitos.
Todos os testes passam.
Lojas respeitam backoff apos rejeicao.
Caminhoes podem quebrar em rota com base no breakdown_risk.
Fabricas e lojas reagem a eventos de caos.
Caminhoes recalculam rota quando bloqueados.
state.md atualizado.
