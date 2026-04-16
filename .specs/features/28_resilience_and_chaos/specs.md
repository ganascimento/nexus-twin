# Feature 28 — Resilience & Chaos

## Objetivo

Fecha os 4 gaps restantes que impedem a simulacao de ser realista: lojas nao respeitam backoff apos rejeicao, caminhoes nunca quebram em rota, fabricas/lojas ignoram eventos de caos, e caminhoes nao recalculam rota quando bloqueados. Cada gap tem infraestrutura parcialmente pronta (DB models, constantes de evento, funcoes de fisica) mas falta a integracao no engine e nos agentes.

---

## Gap A: Retry After Rejection (Backoff da Loja)

### O que existe

- `PendingOrder.retry_after_tick` coluna no banco (models/order.py:20)
- `RejectOrderPayload.retry_after_ticks` no guardrail do warehouse (guardrails/warehouse.py:41-44)
- `OrderService.reject_order()` aceita `retry_after` e grava no banco (services/order.py:25-28)

### O que falta

- Engine nao verifica ordens rejeitadas cujo backoff expirou
- Loja nao recebe trigger para retentar
- Prompt da loja nao menciona retry de ordens rejeitadas

### Solucao

1. `OrderRepository.get_retry_eligible(requester_id, current_tick) -> list[PendingOrder]` — retorna ordens com `status="rejected"` e `age_ticks >= retry_after_tick` (backoff expirou)
2. Engine `_evaluate_triggers()`: para cada loja, verifica se tem ordens elegidas para retry → dispara trigger `order_retry_eligible` com payload da ordem
3. Prompt da loja: adicionar secao `order_retry_eligible` — loja decide se retenta o mesmo armazem ou tenta outro
4. Constante `ORDER_RETRY_ELIGIBLE = "order_retry_eligible"` em events.py
5. Ao retentar: o DecisionEffectProcessor (F24) cria nova PendingOrder (a rejeitada permanece como historico). A deduplicacao de F24 funciona porque a rejeitada nao tem status `pending`/`confirmed`.

### Criterios de Aceitacao

- [ ] `OrderRepository.get_retry_eligible(requester_id, current_tick)` retorna ordens rejeitadas cujo `age_ticks >= retry_after_tick`
- [ ] Engine dispara `order_retry_eligible` para lojas com ordens elegiveis
- [ ] Prompt da loja atualizado com secao `order_retry_eligible` — instrucoes para decidir se retenta mesmo armazem ou tenta outro
- [ ] Constante `ORDER_RETRY_ELIGIBLE` em events.py
- [ ] Apos retry, a ordem rejeitada permanece com status `rejected` — nova PendingOrder e criada

### Testes

- [ ] `test_get_retry_eligible_returns_expired_backoff` — ordem rejeitada com `retry_after_tick=6`, `age_ticks=8` → retornada
- [ ] `test_get_retry_eligible_excludes_active_backoff` — ordem rejeitada com `retry_after_tick=6`, `age_ticks=3` → nao retornada
- [ ] `test_get_retry_eligible_excludes_non_rejected` — ordens pending/confirmed → nao retornadas
- [ ] `test_evaluate_triggers_fires_retry_eligible_for_store` — loja com ordem elegivel → trigger `order_retry_eligible` disparado
- [ ] `test_evaluate_triggers_no_retry_if_backoff_active` — loja com ordem rejeitada mas backoff ativo → nenhum trigger extra

---

## Gap B: Breakdown Risk Roll (Quebra de Caminhao em Rota)

### O que existe

- `TRUCK_BREAKDOWN = "truck_breakdown"` em events.py:6
- `calculate_breakdown_risk(degradation)` em physics.py:31-36
- `is_trip_blocked(degradation)` em physics.py:39-40 (guardrail >= 95%)
- Prompt do caminhao menciona `truck_breakdown` trigger
- Guardrail tem acao `alert_breakdown` (mas sem payload class)

### O que falta

- Engine nunca rola para quebra — `breakdown_risk` e calculado e gravado mas nunca usado
- Nenhum evento `TRUCK_BREAKDOWN` e criado pelo engine
- Payload class para `alert_breakdown` nao existe
- Quando caminhao quebra: carga fica presa, precisa de resgate

### Solucao

1. `roll_breakdown(breakdown_risk) -> bool` em physics.py — `random.random() < breakdown_risk`
2. Engine `_apply_physics()`, no bloco de caminhoes IN_TRANSIT: apos calcular `new_breakdown_risk`, chamar `roll_breakdown()`. Se True:
   - Seta status para `broken`
   - Cria evento `TRUCK_BREAKDOWN` com `entity_type="truck"`, payload com `route_id`, `cargo`, posicao atual
   - Nao limpa cargo (carga fica presa ate resgate)
3. Guardrail: adicionar `ReroutePayload` (ver Gap D) e `AlertBreakdownPayload` com `current_degradation: float`
4. DecisionEffectProcessor (F24): handler para `alert_breakdown` — publica evento de resgate (outro caminhao precisa ser despachado para buscar a carga)

### Criterios de Aceitacao

- [ ] `roll_breakdown(breakdown_risk)` em physics.py — retorna True se `random.random() < breakdown_risk`
- [ ] Engine chama `roll_breakdown` a cada tick para caminhoes IN_TRANSIT
- [ ] Se breakdown: status → `broken`, evento `TRUCK_BREAKDOWN` criado, cargo mantido
- [ ] `AlertBreakdownPayload` adicionado ao guardrail do truck com campo `current_degradation`
- [ ] Quando TruckAgent decide `alert_breakdown` → DecisionEffectProcessor busca outro caminhao para resgatar carga
- [ ] Se nenhum caminhao disponivel para resgate: transport retry sweep (F27) pega no proximo tick
- [ ] Caminhao broken pode receber `request_maintenance` para ser recuperado (status broken → maintenance)

### Testes

- [ ] `test_roll_breakdown_returns_true_when_risk_high` — mock `random.random` retornando 0.1, `breakdown_risk=0.5` → True
- [ ] `test_roll_breakdown_returns_false_when_risk_low` — mock `random.random` retornando 0.9, `breakdown_risk=0.1` → False
- [ ] `test_apply_physics_creates_breakdown_event` — caminhao IN_TRANSIT com breakdown roll True → status `broken`, evento criado, cargo mantido
- [ ] `test_apply_physics_no_breakdown_when_roll_false` — roll False → caminhao continua IN_TRANSIT normalmente
- [ ] `test_alert_breakdown_dispatches_rescue_truck` — DecisionEffectProcessor cria evento para caminhao de resgate

---

## Gap C: Chaos Events para Fabricas e Lojas

### O que existe

- Constantes `MACHINE_BREAKDOWN`, `DEMAND_SPIKE`, `SUDDEN_DEMAND_ZERO` em events.py
- `EventRepository.get_active_for_entity(entity_type, entity_id)` funciona para qualquer tipo
- `ChaosService.inject_event()` cria eventos no banco
- MasterAgent pode injetar `machine_breakdown` e `demand_spike` autonomamente
- Prompts de fabrica e loja mencionam esses triggers (factory.md:41-47, store.md:35-42)

### O que falta

- Engine `_evaluate_triggers()` so verifica eventos ativos para trucks (linhas 284-299). Fabricas e lojas sao ignoradas.
- Quando usuario injeta `machine_breakdown` para uma fabrica, ninguem acorda o agente
- Quando `demand_spike` e injetado para uma loja, ninguem acorda o agente

### Solucao

1. Engine `_evaluate_triggers()`: adicionar blocos de verificacao de eventos ativos para fabricas e lojas (mesmo padrao dos trucks):
   ```python
   for factory in world_state.factories:
       active_events = await event_repo.get_active_for_entity("factory", factory.id)
       if active_events:
           triggers.append((_make_agent_callable("factory", factory.id), ...))
   
   for store in world_state.stores:
       active_events = await event_repo.get_active_for_entity("store", store.id)
       if active_events:
           triggers.append((_make_agent_callable("store", store.id), ...))
   ```
2. O evento e passado como trigger — o agente recebe `event_type` no `trigger_event` do AgentState
3. Engine resolve o evento apos criar o trigger (evita re-trigger a cada tick)
4. Para `machine_breakdown`: fabrica precisa reduzir/parar producao. FactoryDecision ja tem acao `stop_production`.
5. Para `demand_spike`: loja precisa ajustar pedidos. StoreDecision ja tem `order_replenishment` com quantidade ajustada.
6. DecisionEffectProcessor (F24): handler para `stop_production` → `FactoryRepository.update_production_rate(factory_id, material_id, 0.0)`

### Criterios de Aceitacao

- [ ] Engine verifica eventos ativos para fabricas e dispara trigger com `event_type` do evento
- [ ] Engine verifica eventos ativos para lojas e dispara trigger com `event_type` do evento
- [ ] Engine resolve o evento apos criar o trigger (seta `status="resolved"`, `tick_end=current_tick`)
- [ ] FactoryAgent recebe `machine_breakdown` e pode decidir `stop_production`
- [ ] StoreAgent recebe `demand_spike` e pode decidir `order_replenishment` com quantidade ajustada
- [ ] DecisionEffectProcessor: `stop_production` → para producao do material afetado
- [ ] Warehouse agent triggers (F25) tambem passam por verificacao de eventos ativos (se houver)

### Testes

- [ ] `test_evaluate_triggers_fires_for_factory_chaos_event` — fabrica com evento ativo `machine_breakdown` → trigger disparado com event_type correto
- [ ] `test_evaluate_triggers_fires_for_store_chaos_event` — loja com evento ativo `demand_spike` → trigger disparado
- [ ] `test_evaluate_triggers_resolves_event_after_trigger` — apos criar trigger → evento marcado como `resolved`
- [ ] `test_evaluate_triggers_does_not_retrigger_resolved_event` — evento resolvido → nao dispara novamente
- [ ] `test_stop_production_handler` — DecisionEffectProcessor recebe `stop_production` → `update_production_rate` chamado com rate=0

---

## Gap D: Reroute Quando Route Blocked

### O que existe

- `ROUTE_BLOCKED = "route_blocked"` em events.py:4
- Prompt do truck descreve `route_blocked` trigger e acao `reroute` (truck.md:34, 58, 92-94)
- `RouteService.compute_route()` calcula nova rota via Valhalla

### O que falta

- Guardrail nao tem `reroute` como acao valida (truck.py:34-38 lista: accept_contract, refuse_contract, choose_route, request_maintenance, alert_breakdown, complete_delivery)
- Nao existe `ReroutePayload` class
- DecisionEffectProcessor nao tem handler para `reroute`
- Engine nao cria `route_blocked` quando uma rota e bloqueada por chaos event

### Solucao

1. Guardrail: adicionar `reroute` a lista de acoes validas em `TruckDecision`
2. Criar `ReroutePayload(BaseModel)` com `order_id: str`, `reason: str`
3. DecisionEffectProcessor handler `_handle_reroute`:
   - Busca posicao atual do caminhao
   - Busca destino da rota ativa
   - Chama `RouteService.compute_route()` com posicao atual → destino
   - Atualiza rota ativa com novo path/timestamps/eta_ticks via `RouteRepository.update_route_data()`
4. `RouteRepository.update_route_data(route_id, path, timestamps, eta_ticks)` — atualiza rota existente
5. Engine: quando existe evento `route_blocked` que afeta uma rodovia, verificar quais caminhoes IN_TRANSIT tem rotas que passam por ela → criar evento `ROUTE_BLOCKED` com `entity_type="truck"`, `entity_id=truck.id`
6. A logica de deteccao de rotas afetadas pode ser simplificada: `route_blocked` chaos event contem `payload.highway` ou `payload.affected_area` → engine compara com `route.path` dos caminhoes em transito

### Criterios de Aceitacao

- [ ] `reroute` adicionado a lista de acoes validas em `TruckDecision`
- [ ] `ReroutePayload` com `order_id: str` e `reason: str`
- [ ] DecisionEffectProcessor handler `_handle_reroute` recalcula rota via Valhalla e atualiza rota ativa
- [ ] `RouteRepository.update_route_data(route_id, path, timestamps, eta_ticks)` atualiza rota existente
- [ ] Engine detecta caminhoes afetados por `route_blocked` e cria eventos individuais
- [ ] TruckAgent recebe `route_blocked` e pode decidir `reroute` ou `request_maintenance` (se muito degradado)

### Testes

- [ ] `test_reroute_action_accepted_by_guardrail` — `TruckDecision(action="reroute", payload={"order_id": "...", "reason": "route_blocked"})` nao levanta ValidationError
- [ ] `test_handle_reroute_computes_new_route` — DecisionEffectProcessor chama `RouteService.compute_route` com posicao atual do caminhao e destino da rota
- [ ] `test_handle_reroute_updates_active_route` — `RouteRepository.update_route_data` chamado com novos path/timestamps/eta_ticks
- [ ] `test_evaluate_triggers_creates_route_blocked_for_affected_trucks` — evento `route_blocked` ativo + caminhao com rota passando pela area afetada → trigger criado para o caminhao
- [ ] `test_evaluate_triggers_ignores_trucks_not_on_blocked_route` — caminhao com rota diferente → nenhum trigger

---

## Fora do Escopo

- Logica complexa de matching de rotas bloqueadas com geometria exata (simplificar para comparacao basica)
- Resgate de carga com transferencia entre caminhoes (simplificar: novo caminhao e despachado, carga do broken e perdida ou fica parada)
- Chaos events compostos (ex: tempestade + route_blocked simultaneos)
- Dashboard/frontend para visualizar eventos de resiliencia
- Backoff escalonado (PRD menciona aumentar backoff na segunda rejeicao — simplificar para retry simples)
