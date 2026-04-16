# Feature 23 — Agent Wiring + End-to-End Integration Tests

## Objetivo

Conectar os agentes LangGraph ao engine de simulação (atualmente `agent_fn` é sempre `None`) e implementar testes de integração end-to-end que validam o fluxo completo: engine tick → trigger evaluation → agent dispatch → perceive → LLM (mockado) → guardrail → persist decision → publish → efeitos no mundo.

Cada teste usa `FakeListChatModel` com respostas JSON pré-definidas, PostgreSQL real (testcontainers), e Redis mockado. O objetivo é provar que a cadeia inteira funciona — da detecção do trigger até a decisão persistida no banco e seus efeitos downstream.

---

## Escopo

### Parte 1 — Agent Wiring (implementação)

Conectar os agentes ao engine para que `_dispatch_agent` receba callables reais em vez de `None`:

1. **Engine `_evaluate_triggers`** — substituir `(None, event)` por `(agent_callable, event)` onde `agent_callable` é uma função que instancia o agente correto e chama `run_cycle(event)`
2. **Agent factory** — criar uma factory function no engine que, dado `entity_type` + `entity_id` + `event`, constrói o agente correto (StoreAgent, WarehouseAgent, FactoryAgent, TruckAgent) com session e publisher, e chama `run_cycle`
3. **Redis publisher** — a instância do Redis client do engine deve ser passada para os agentes como publisher

### Parte 2 — Testes E2E (entregável principal)

Cenários end-to-end com LLM mockado que validam o fluxo completo.

---

## Cenários de Teste

### Cenário 1 — Store replenishment flow

**Setup:** Seed world, reduzir estoque da store-001/cimento para abaixo do reorder_point.

**LLM mock retorna:**
```json
{"action": "order_replenishment", "payload": {"material_id": "cimento", "quantity_tons": 30.0, "from_warehouse_id": "warehouse-002"}, "reasoning_summary": "Stock below reorder point"}
```

**Validações:**
- [ ] POST /tick completa sem erro
- [ ] `agent_decisions` contém registro com `entity_id=store-001`, `action=order_replenishment`
- [ ] `pending_orders` contém pedido com `requester_id=store-001`, `material_id=cimento`, `target_id=warehouse-002`

### Cenário 2 — Warehouse resupply flow

**Setup:** Seed, reduzir estoque warehouse-001/vergalhao para abaixo de min_stock.

**LLM mock retorna:**
```json
{"action": "request_resupply", "payload": {"material_id": "vergalhao", "quantity_tons": 200.0, "from_factory_id": "factory-002"}, "reasoning_summary": "Stock critically low"}
```

**Validações:**
- [ ] `agent_decisions` contém registro com `entity_id=warehouse-001`, `action=request_resupply`
- [ ] `pending_orders` contém pedido com `requester_type=warehouse`, `target_type=factory`

### Cenário 3 — Factory production flow

**Setup:** Seed, reduzir estoque factory-003/cimento para < 30% do max, production_rate_current=0.

**LLM mock retorna:**
```json
{"action": "start_production", "payload": {"material_id": "cimento", "quantity_tons": 25.0}, "reasoning_summary": "Urgent resupply needed"}
```

**Validações:**
- [ ] `agent_decisions` contém registro com `entity_id=factory-003`, `action=start_production`
- [ ] `factory_products.production_rate_current` foi atualizado no banco

### Cenário 4 — Truck maintenance flow

**Setup:** Seed, setar truck-006 com degradation=0.96 (acima do guardrail 0.95).

**Esperado:** Fast-path do agente bloqueia viagem e força `request_maintenance`.

**Validações:**
- [ ] `agent_decisions` contém registro com `action=request_maintenance`
- [ ] Truck status muda para `maintenance`

### Cenário 5 — Guardrail rejects invalid LLM response

**Setup:** Store com estoque baixo (trigger dispara).

**LLM mock retorna ação inválida:**
```json
{"action": "fly_to_moon", "payload": {}, "reasoning_summary": "Invalid"}
```

**Validações:**
- [ ] Tick completa sem crashar (engine resiliente)
- [ ] NENHUM `agent_decisions` criado para essa store
- [ ] NENHUM `pending_orders` criado

### Cenário 6 — Multi-tick supply chain flow

**Setup:** Seed com estoques normais. Avançar N ticks até uma loja cruzar o threshold.

**LLM mock retorna:** `order_replenishment` quando chamado.

**Validações:**
- [ ] Estoques das lojas diminuem progressivamente a cada tick
- [ ] Em algum tick, o trigger dispara e o agente cria um `pending_order`
- [ ] `age_ticks` do pedido incrementa nos ticks subsequentes
- [ ] Redis recebe publish de `world_state` a cada tick e `agent_decisions` quando agente age

### Cenário 7 — Store fast-path emergency order

**Setup:** Store com estoque de um produto < 10% do reorder_point (zona crítica).

**Esperado:** Fast-path dispara `order_replenishment` sem chamar o LLM.

**Validações:**
- [ ] `agent_decisions` contém registro com a ação de emergência
- [ ] LLM NÃO foi chamado (FakeListChatModel não consumiu nenhuma resposta)

### Cenário 8 — Store fast-path hold (stock comfortable)

**Setup:** Store com estoque > 85% do stock_max equivalente.

**Esperado:** Fast-path dispara `hold` sem chamar o LLM.

**Validações:**
- [ ] `agent_decisions` contém `action=hold`
- [ ] Nenhum `pending_orders` criado

---

## Infraestrutura de Teste

### Fixtures

- `seeded_simulation_client` existente (feature 22) — truncate + seed + engine com mock_redis
- LLM mockado via `patch("src.agents.base.ChatOpenAI", ...)` com `FakeListChatModel`
- Cada teste precisa aguardar agents completarem (fire-and-forget) com `await asyncio.sleep(0.5)` após o tick

### Mocking Strategy

| Camada | Real/Mock |
|---|---|
| PostgreSQL | **Real** (testcontainers) |
| Engine + Physics | **Real** |
| Agent Graph (LangGraph) | **Real** |
| Guardrails (Pydantic) | **Real** |
| ChatOpenAI (LLM) | **Mock** (FakeListChatModel) |
| Agent Tools | **Mock** (retornam dados fixos) |
| Redis Pub/Sub | **Mock** (AsyncMock) |
| Valhalla HTTP | **Mock** (se truck routing for testado) |

---

## Estrutura de Arquivos

```
backend/tests/integration/
├── simulation/
│   ├── conftest.py                          # Fixtures existentes (feature 22)
│   ├── test_simulation_lifecycle.py         # Feature 22
│   ├── test_physics_integration.py          # Feature 22
│   ├── test_triggers_integration.py         # Feature 22
│   ├── test_multi_tick_flow.py              # Feature 22
│   └── test_agent_e2e.py                    # Feature 23 — NOVO
```

### Arquivos de produção modificados

```
backend/src/
├── simulation/
│   └── engine.py                            # Wiring: agent dispatch com callables reais
```
