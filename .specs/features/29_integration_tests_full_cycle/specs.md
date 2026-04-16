# Feature 29 — Integration Tests: Full Cycle

## Objetivo

Testes de integracao pesados que validam o ciclo completo da simulacao de ponta a ponta. Cada teste roda multiplos ticks contra banco PostgreSQL real (testcontainers), com LLM mockado via `FakeMessagesListChatModel`, e verifica que decisoes de agentes geram efeitos reais no mundo: PendingOrders criados, estoque transferido, caminhoes em transito, entregas completadas.

Os testes existentes em `test_agent_e2e.py` so verificam que agentes **criam decisoes**. Estes testes verificam que decisoes **mudam o estado do mundo** — cobrindo F24 a F28 como um todo.

### Principios

- **Banco real:** PostgreSQL via testcontainers — sem mocks de banco
- **LLM mockado:** `FakeMessagesListChatModel` retorna respostas pre-definidas por cenario
- **Multi-tick:** cada cenario roda N ticks e verifica estado intermediario e final
- **Valhalla mockado:** `RouteService.compute_route` mockado para retornar rota fixa (sem dependencia de infra geo)
- **Redis mockado:** publisher mockado (nao testa WebSocket, so efeitos no banco)
- **Seed completo:** usa `seed_default_world` como base e ajusta estoques por cenario

---

## Cenarios de Teste

### Cenario 1 — Ciclo Store→Warehouse→Truck→Delivery (happy path)

Fluxo completo de reposicao quando warehouse tem estoque.

**Setup:**
- Seed padrao
- Store-001 estoque de cimento = 1.0 ton (abaixo do reorder_point de 15 ton)
- Warehouse-002 estoque de cimento = 150 ton (suficiente)
- Truck-004 (terceiro) idle em SP

**LLM responses pre-programadas** (uma por agente por tick):
- StoreAgent: `{"action": "order_replenishment", "payload": {"material_id": "cimento", "quantity_tons": 30, "from_warehouse_id": "warehouse-002"}}`
- WarehouseAgent: `{"action": "confirm_order", "payload": {"order_id": "<dynamic>", "quantity_tons": 30, "eta_ticks": 3}}`
- TruckAgent: `{"action": "accept_contract", "payload": {"order_id": "<dynamic>", "chosen_route_risk_level": "low"}}`

**Verificacoes por tick:**

| Tick | Verifica |
|------|----------|
| 1 | `agent_decisions` tem `order_replenishment` de store-001. `pending_orders` tem 1 registro com status=pending, target=warehouse-002 |
| 2 | `agent_decisions` tem `confirm_order` de warehouse-002. `pending_orders` status=confirmed. `warehouse_stocks` cimento stock_reserved += 30. Evento `contract_proposal` existe para um truck |
| 3 | `agent_decisions` tem `accept_contract` de truck. `routes` tem 1 rota ativa. `trucks` truck_id status=in_transit |
| 4-N | `trucks` posicao atualizada. `routes` eta_ticks decrementa |
| N+1 | `trucks` status=idle, cargo=null. `store_stocks` cimento += 30. `pending_orders` status=delivered. `warehouse_stocks` stock_reserved -= 30 |

**Testes:**
- [ ] `test_full_cycle_store_to_delivery` — roda N ticks ate entrega, verifica estado final
- [ ] `test_pending_order_created_after_store_decision` — tick 1 cria PendingOrder
- [ ] `test_warehouse_reserves_stock_on_confirm` — tick 2 incrementa stock_reserved
- [ ] `test_truck_assigned_route_on_accept` — tick 3 cria rota e muda status
- [ ] `test_stock_transferred_to_store_on_arrival` — tick final transfere estoque
- [ ] `test_order_marked_delivered_on_arrival` — tick final muda status para delivered

### Cenario 2 — Cadeia completa Store→Warehouse→Factory→Truck→Warehouse→Truck→Store

Fluxo quando warehouse nao tem estoque e precisa pedir a fabrica.

**Setup:**
- Store-001 cimento = 1.0 ton
- Warehouse-002 cimento = 0 ton (vazio)
- Factory-003 cimento = 400 ton (tem estoque)
- Truck-002 (proprietario factory-003) idle
- Truck-004 (terceiro) idle

**LLM responses:**
- StoreAgent: `order_replenishment` → warehouse-002
- WarehouseAgent (order_received): `reject_order` (estoque insuficiente)
- WarehouseAgent (stock_trigger): `request_resupply` → factory-003
- FactoryAgent (resupply_requested): `send_stock` → warehouse-002
- TruckAgent-002 (new_order): `accept_contract` (proprietario)
- WarehouseAgent (resupply_delivered): `confirm_order` (agora tem estoque)
- TruckAgent-004 (contract_proposal): `accept_contract` (terceiro, warehouse→store)

**Verificacoes:**
- [ ] `test_full_chain_factory_to_store` — roda ~15-20 ticks, verifica: warehouse recebeu estoque da fabrica, depois loja recebeu estoque do warehouse
- [ ] `test_factory_order_created_on_resupply` — PendingOrder criado de warehouse para factory
- [ ] `test_factory_stock_decremented_on_send` — estoque da fabrica diminui apos send_stock
- [ ] `test_warehouse_stock_increased_after_delivery` — estoque do warehouse aumenta quando caminhao chega

### Cenario 3 — Manutencao: entrada e saida

**Setup:**
- Truck-006 (terceiro) idle, degradation=0.75
- Nenhum trigger de estoque (mundo estavel)

**LLM response:**
- TruckAgent: `{"action": "request_maintenance", "payload": {"current_degradation": 0.75}}`

**Verificacoes:**
- [ ] `test_maintenance_entry_and_exit` — tick 1: truck status=maintenance, degradation=0. Roda N ticks (duration para 75% = 8 ticks). Apos 8 ticks: truck status=idle
- [ ] `test_maintenance_duration_matches_degradation` — verifica que duracao respeita a tabela do PRD

### Cenario 4 — Transport retry: ordem sem caminhao disponivel

**Setup:**
- Store-001 cimento = 1.0 ton
- Warehouse-002 cimento = 150 ton
- Todos os caminhoes em IN_TRANSIT ou MAINTENANCE (nenhum idle)

**LLM responses:**
- StoreAgent: `order_replenishment`
- WarehouseAgent: `confirm_order`

**Verificacoes:**
- [ ] `test_transport_retry_when_no_truck` — tick 1-2: ordem confirmed mas sem rota (nenhum truck idle). Muda um truck para idle. Proximo tick: transport retry sweep cria evento, truck aceita, rota criada
- [ ] `test_confirmed_order_not_lost` — ordem permanece confirmed durante multiplos ticks sem truck

### Cenario 5 — Rejeicao + backoff + retry

**Setup:**
- Store-001 cimento = 1.0 ton
- Warehouse-002 cimento = 0 ton

**LLM responses:**
- StoreAgent: `order_replenishment` → warehouse-002
- WarehouseAgent: `reject_order` com `retry_after_ticks: 5`
- StoreAgent (retry): `order_replenishment` → warehouse-002 (ou outro warehouse)

**Verificacoes:**
- [ ] `test_rejected_order_respects_backoff` — ordem rejeitada em tick 3. Ticks 4-7: loja NAO recebe trigger de retry. Tick 8 (age_ticks >= retry_after_tick): loja recebe trigger `order_retry_eligible`
- [ ] `test_retry_creates_new_order` — apos retry, nova PendingOrder criada. Antiga permanece rejected.

### Cenario 6 — Breakdown mid-route

**Setup:**
- Truck-006 degradation=0.85, IN_TRANSIT com rota ativa e cargo

**Verificacoes:**
- [ ] `test_breakdown_stops_truck` — mock `random.random` < breakdown_risk → truck status=broken, evento truck_breakdown criado, cargo mantido
- [ ] `test_broken_truck_cargo_not_lost` — cargo permanece no truck apos breakdown

### Cenario 7 — Chaos: machine_breakdown na fabrica

**Setup:**
- Factory-001 operating, producao ativa

**Acao:** Injetar evento `machine_breakdown` via API `/chaos/events`

**LLM response:**
- FactoryAgent: `stop_production`

**Verificacoes:**
- [ ] `test_chaos_machine_breakdown_triggers_factory` — apos injecao + tick, factory agent decide stop_production
- [ ] `test_production_stopped_after_chaos` — production_rate_current = 0 para o produto afetado

### Cenario 8 — Chaos: demand_spike na loja

**Setup:**
- Store-001 estoque saudavel

**Acao:** Injetar evento `demand_spike` via API

**LLM response:**
- StoreAgent: `order_replenishment` com quantity maior

**Verificacoes:**
- [ ] `test_chaos_demand_spike_triggers_store` — store agent acorda e faz pedido

### Cenario 9 — Deduplicacao: loja nao duplica pedidos

**Setup:**
- Store-001 cimento baixo
- Rodar 3 ticks com estoque baixo

**Verificacoes:**
- [ ] `test_store_does_not_duplicate_orders` — apenas 1 PendingOrder ativo (pending ou confirmed) por material+requester, mesmo apos 3 ticks

### Cenario 10 — Concorrencia: multiplas lojas pedem ao mesmo warehouse

**Setup:**
- Store-001 e Store-002 ambas com cimento baixo
- Warehouse-002 tem 40 ton (suficiente para 1, nao para 2 de 30)

**Verificacoes:**
- [ ] `test_concurrent_orders_atomic_reserve` — uma ordem confirmed, outra rejected (ou ambas com quantidades ajustadas). stock_reserved nunca excede stock disponivel

---

## Estrutura de Arquivos

```
backend/tests/integration/simulation/
├── test_full_cycle.py          # Cenarios 1, 2
├── test_maintenance_cycle.py   # Cenario 3
├── test_transport_retry.py     # Cenario 4
├── test_retry_backoff.py       # Cenario 5
├── test_breakdown_cycle.py     # Cenario 6
├── test_chaos_integration.py   # Cenarios 7, 8
├── test_deduplication.py       # Cenario 9
├── test_concurrency.py         # Cenario 10
```

---

## Helpers Necessarios

### `conftest.py` — fixtures adicionais

- `fake_valhalla_route` — mock de `RouteService.compute_route` retornando rota fixa com 5 waypoints e ETA de 3 ticks
- `make_llm_sequence(responses: list[dict])` — cria `FakeMessagesListChatModel` que retorna respostas na ordem (uma por chamada). Permite programar respostas diferentes por agente ao longo de multiplos ticks.
- `advance_ticks_with_settle(client, n, settle_time=2.0)` — avanca N ticks com `asyncio.sleep` entre eles para agents fire-and-forget completarem
- `assert_order_status(session, order_id, expected_status)` — helper de verificacao
- `assert_truck_status(session, truck_id, expected_status)` — helper
- `assert_stock(session, entity_type, entity_id, material_id, expected_stock)` — helper

### LLM por agente

O `FakeMessagesListChatModel` retorna respostas na ordem da lista, independente de qual agente chama. Para controlar respostas por agente, usar `patch` seletivo no `ChatOpenAI` com side_effect que retorna LLM diferente baseado no contexto, ou programar a sequencia na ordem correta em que os agentes serao disparados.

Alternativa mais simples: como o engine dispara agentes em ordem previsivel (stores → warehouses → factories → trucks), programar a lista de respostas nessa ordem.

---

## Pre-requisitos

- F24 (DecisionEffectProcessor) implementado
- F25 (Order-based triggers) implementado
- F26 (Delivery completion) implementado
- F27 (Maintenance + transport retry) implementado
- F28 (Resilience & chaos) implementado

**Esta feature NAO implementa codigo de producao.** Apenas testes. Se um teste falhar, o bug esta em F24-F28, nao nesta feature.

---

## Fora do Escopo

- Testes de frontend/WebSocket
- Testes com Valhalla real (sempre mockado)
- Testes com OpenAI real (sempre FakeListChatModel)
- Testes de performance/carga
- Testes de chaos compostos (multiplos eventos simultaneos)
