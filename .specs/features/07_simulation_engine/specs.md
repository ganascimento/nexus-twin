# Feature 07 — Simulation Engine

## Objetivo

Implementar o núcleo da simulação: o loop de ticks que avança o mundo a cada intervalo de tempo real, calcula a física determinística (posições, estoques, degradação), avalia os gatilhos preditivos dos agentes e despacha ciclos de agente via `asyncio.create_task` (fire-and-forget). Esta feature também entrega os tipos de evento (`events.py`), o publisher Redis (`publisher.py`) e a interface de injeção de caos (`chaos.py`).

Sem esta feature, nada se move — ela é o coração do mundo simulado. Features de agentes (08–12), API de simulação (13), WebSocket (14) e Celery (15) dependem diretamente da engine estar funcional.

---

## Critérios de Aceitação

### Engine — `simulation/engine.py`

- [ ] A função `run_tick()` executa na seguinte ordem: carrega `WorldState` via `WorldStateService`, chama `apply_physics()`, chama `evaluate_triggers()`, dispara agentes ativos via `asyncio.create_task()`, publica via `publisher.py`, incrementa o contador de ticks — sem exceção a esta ordem
- [ ] O loop principal aceita `tick_interval_seconds` ajustável (mínimo 10), lido de `TICK_INTERVAL_SECONDS` do ambiente como padrão
- [ ] `apply_physics()` avança a posição de cada caminhão com `status = in_transit` ao longo do `path` da rota ativa com base no timestamp atual; caminhões que chegam ao destino final são marcados como `idle` e o cargo é zerado
- [ ] `apply_physics()` decrementa o estoque de cada `StoreStock` por `demand_rate` a cada tick; o estoque não vai abaixo de `0.0`
- [ ] `apply_physics()` incrementa o estoque de cada `FactoryProduct` por `production_rate_current` a cada tick; o estoque não ultrapassa `stock_max` — se atingir o teto, `production_rate_current` é zerado automaticamente para aquele produto
- [ ] `apply_physics()` incrementa `degradation` de caminhões `in_transit` proporcionalmente à distância percorrida no tick e ao peso de `cargo.quantity`; `breakdown_risk` cresce exponencialmente acima de `0.7` de degradação
- [ ] `apply_physics()` bloqueia qualquer nova viagem de caminhão com `degradation >= 0.95` — independente da decisão de qualquer agente; o status do caminhão permanece `idle` e o engine registra o bloqueio como evento `engine_blocked_degraded_truck`
- [ ] `apply_physics()` incrementa `age_ticks` de todos os `PendingOrder` com status `pending` ou `confirmed`
- [ ] `evaluate_triggers()` avalia para cada loja, para cada produto `p` gerenciado: `(stock[p] - reorder_point[p]) / demand_rate[p] < lead_time_ticks × 1.5`; agentes acordam apenas quando a condição é verdadeira
- [ ] `evaluate_triggers()` avalia para cada armazém, para cada produto `p`: `(stock[p] - min_stock[p]) / demand_rate_estimate[p] < lead_time_ticks × 1.5`; `demand_rate_estimate` é calculado como a soma das `demand_rate` das lojas atendidas por esse armazém para o produto `p`
- [ ] `evaluate_triggers()` acorda o agente de caminhão quando há evento pendente do tipo `route_blocked`, `truck_arrived`, `truck_breakdown` ou `new_order` (proprietário) / `contract_proposal` (terceiro); caminhões `in_transit` sem evento pendente não acordam
- [ ] Agentes despachados rodam via `asyncio.create_task()` — o tick não aguarda conclusão; o retorno de `run_tick()` não bloqueia na resolução dos agentes
- [ ] `asyncio.Semaphore(MAX_AGENT_WORKERS)` controla a concorrência de chamadas aos agentes; `MAX_AGENT_WORKERS` é lido do ambiente
- [ ] O engine expõe `start()`, `stop()` e `advance_one_tick()` como métodos públicos; `advance_one_tick()` funciona somente quando o loop está parado

### Eventos — `simulation/events.py`

- [ ] Todos os tipos de evento do sistema estão definidos como constantes ou enum: `route_blocked`, `truck_arrived`, `truck_breakdown`, `new_order`, `contract_proposal`, `machine_breakdown`, `demand_spike`, `strike`, `storm`, `sudden_demand_zero`, `engine_blocked_degraded_truck`, `low_stock_trigger`, `stock_trigger_warehouse`, `stock_trigger_factory`
- [ ] O módulo define `SimulationEvent` — dataclass com campos: `event_type: str`, `source: str` (`user` / `master_agent` / `engine`), `entity_type: str | None`, `entity_id: str | None`, `payload: dict`, `tick: int`
- [ ] O módulo define `route_event()`, `trigger_event()` e `chaos_event()` como funções de fábrica que constroem `SimulationEvent` com os campos corretos — sem lógica de negócio

### Publisher — `simulation/publisher.py`

- [ ] `publish_world_state(world_state: WorldState, tick: int)` serializa o `WorldState` como JSON e publica no canal `nexus:world_state`
- [ ] `publish_agent_decision(decision: dict, tick: int)` publica no canal `nexus:agent_decisions`
- [ ] `publish_event(event: SimulationEvent)` publica no canal `nexus:events`
- [ ] O publisher não cria conexão Redis no momento do import — a conexão é obtida via injeção ou context manager a cada chamada
- [ ] Falhas de conexão Redis são logadas via Loguru mas não propagam exceção — o tick não para por falha no publisher

### Caos — `simulation/chaos.py`

- [ ] `inject_chaos_event(event_type, payload, source, entity_type, entity_id, tick)` persiste um `ChaosEvent` no banco com `status = active` e publica no canal `nexus:events`
- [ ] Eventos exclusivamente manuais (`strike`, `route_blocked`, `storm`, `sudden_demand_zero`) rejeitam injeção quando `source = master_agent` — retornam erro descritivo sem persistir
- [ ] `resolve_chaos_event(event_id, tick)` atualiza `status = resolved` e `tick_end` no banco
- [ ] O módulo expõe `can_inject_autonomous_event(current_tick)` que retorna `False` quando: (a) há algum evento autônomo com `status = active`, ou (b) o último evento autônomo foi resolvido há menos de 24 ticks; retorna `True` caso contrário
- [ ] Nenhuma lógica de decisão de *quando* injetar — isso é responsabilidade do `MasterAgent` (feature 09)

---

## Fora do Escopo

- Implementação dos agentes LLM (`factory_agent.py`, etc.) — feature 08 e 09
- Guardrails de decisão (`guardrails/`) — feature 10
- Ferramentas dos agentes (`tools/`) — feature 11
- API REST para controle da simulação (`/simulation/start`, `/simulation/stop`) — feature 13
- WebSocket streaming para o dashboard (`api/websocket.py`) — feature 14
- Celery workers para relatórios e exportações — feature 15
- Integração com Valhalla para cálculo de rotas reais — feature 06 (RouteService)
- Persistência de decisões dos agentes (`agent_decision.py`) — responsabilidade do `act` node dos agentes (feature 09)
