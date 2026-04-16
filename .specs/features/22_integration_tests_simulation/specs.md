# Feature 22 — Integration Tests: Simulation Lifecycle & Agent Flow

## Objetivo

Implementar testes de integração que validam o ciclo de vida da simulação (start, stop, tick, speed) e o fluxo end-to-end dos agentes com LLM mockado. Estes testes garantem que a cadeia completa funciona: engine → physics → triggers → agent dispatch → LLM (mockado) → guardrail → persist decision → publish.

O LLM é substituído pelo `FakeListChatModel` do LangChain, que retorna respostas JSON pré-definidas. Isso permite:
1. **Zero custo de token** — nenhuma chamada real à OpenAI
2. **Determinismo** — a mesma resposta sempre, sem variação
3. **Validação comportamental** — dado um input específico do mundo e uma resposta específica do LLM, verificar que o sistema se comporta corretamente (persiste a decisão certa, atualiza o estoque certo, publica o evento certo)

---

## Escopo

### Cenários cobertos

1. **Simulation Lifecycle** — start, stop, advance tick, speed control
2. **Physics Tick** — estoques decrementam, production rates aplicam, degradação calcula
3. **Trigger Evaluation** — triggers disparam para entidades com estoque projetado abaixo do mínimo
4. **Store Agent Flow** — loja com estoque baixo → agente acorda → LLM decide `order_replenishment` → pedido criado
5. **Warehouse Agent Flow** — armazém com estoque crítico → agente acorda → LLM decide `request_resupply` → pedido criado
6. **Factory Agent Flow** — fábrica com pedido urgente → agente acorda → LLM decide `start_production` → production rate atualizado
7. **Truck Agent Flow (proprietário)** — recebe ordem → LLM decide `accept_contract` → rota criada (Valhalla mockado)
8. **Truck Agent Flow (terceiro)** — proposta de contrato → LLM decide `refuse_contract` → motivo registrado
9. **Guardrail Rejection** — LLM retorna decisão inválida → guardrail rejeita → nada persiste

### O que NÃO está no escopo

- Testes de CRUD de entidades (feature 21)
- Testes de WebSocket streaming (unit tests existentes)
- Testes com LLM real (custo proibitivo)
- Testes de chaos injection (cobertos em unit tests do ChaosService)

---

## Infraestrutura de Teste

### PostgreSQL via testcontainers

Mesma infraestrutura da feature 21 — `postgres_container`, `async_engine`, `async_session`.

### LLM Mockado — FakeListChatModel

```python
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

def fake_llm(*responses: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=r) for r in responses]
    )
```

Cada teste define a resposta exata que o LLM "retorna". O sistema processa essa resposta normalmente (guardrail, persist, publish). O teste valida o comportamento downstream.

### Redis Mockado

Redis é mockado com `AsyncMock()` — publish calls são capturadas para assertion sem precisar de container Redis.

### Valhalla Mockado

Chamadas HTTP ao Valhalla (route calculation) são mockadas com `httpx` mock ou `respx` para retornar uma rota fixa.

---

## Critérios de Aceitação

### Simulation Lifecycle — `test_simulation_lifecycle.py`

- [ ] `POST /simulation/start` → status muda para running, retorna 200
- [ ] `GET /simulation/status` → retorna `{"status": "running", ...}` após start
- [ ] `POST /simulation/stop` → para a simulação, retorna 200
- [ ] `GET /simulation/status` → retorna `{"status": "stopped", ...}` após stop
- [ ] `POST /simulation/tick` → avança 1 tick manualmente quando parado
- [ ] `POST /simulation/tick` → tick counter incrementa (GET status confirma)
- [ ] `POST /simulation/tick` → retorna 409 se simulação está rodando
- [ ] `PATCH /simulation/speed` com `{"tick_interval_seconds": 15}` → atualiza velocidade
- [ ] `PATCH /simulation/speed` com valor < 10 → mantém mínimo de 10

### Physics Tick — `test_physics_integration.py`

- [ ] Após 1 tick, estoques das lojas decrementam pelo `demand_rate` de cada produto
- [ ] Após 1 tick, fábricas com `production_rate_current > 0` incrementam estoque do produto
- [ ] Fábrica com `stock >= stock_max` para a produção daquele produto automaticamente
- [ ] Caminhão `in_transit` com `eta_ticks=1` é movido para `idle` após o tick
- [ ] Caminhão `in_transit` tem posição interpolada corretamente ao longo da rota
- [ ] `pending_orders.age_ticks` incrementa para todos os pedidos ativos

### Trigger Evaluation — `test_triggers_integration.py`

- [ ] Loja com `(stock - reorder_point) / demand_rate < lead_time × 1.5` gera trigger
- [ ] Loja com estoque confortável (acima do threshold) NÃO gera trigger
- [ ] Armazém com estoque disponível (`stock - stock_reserved`) <= `min_stock × 1.2` gera trigger
- [ ] Fábrica com `stock / stock_max < 0.3` e `production_rate_current == 0` gera trigger
- [ ] Caminhão com evento ativo na tabela events gera trigger

### Store Agent End-to-End — `test_store_agent_e2e.py`

Setup: seed + manipular estoque da loja para ficar abaixo do reorder_point.

- [ ] LLM mockado retorna `{"action": "order_replenishment", "payload": {"material_id": "cimento", "quantity_tons": 30, "from_warehouse_id": "warehouse-002"}, "reasoning_summary": "Stock projection below reorder point"}`
- [ ] Após o ciclo do agente, um `pending_order` é criado na tabela com os valores corretos
- [ ] `agent_decisions` contém registro com `action=order_replenishment`, `entity_id=store-001`
- [ ] A decisão publicada no Redis contém os campos esperados

### Warehouse Agent End-to-End — `test_warehouse_agent_e2e.py`

Setup: seed + reduzir estoque do armazém para abaixo de `min_stock`.

- [ ] LLM mockado retorna `{"action": "request_resupply", "payload": {"material_id": "vergalhao", "quantity_tons": 200, "from_factory_id": "factory-002"}, "reasoning_summary": "Stock critically low"}`
- [ ] Após o ciclo, `pending_order` criado com `requester_type=warehouse`, `target_type=factory`
- [ ] `agent_decisions` contém registro correto

### Factory Agent End-to-End — `test_factory_agent_e2e.py`

Setup: seed + estoque baixo + production_rate_current = 0.

- [ ] LLM mockado retorna `{"action": "start_production", "payload": {"material_id": "cimento", "quantity_tons": 25}, "reasoning_summary": "Urgent resupply needed"}`
- [ ] Após o ciclo, `production_rate_current` do produto é atualizado no banco
- [ ] `agent_decisions` contém registro correto

### Truck Agent End-to-End — `test_truck_agent_e2e.py`

- [ ] **Proprietário aceita ordem:** LLM retorna `accept_contract` → truck status muda para `in_transit`, rota criada
- [ ] **Terceiro recusa contrato:** LLM retorna `refuse_contract` com motivo → truck permanece `idle`, motivo registrado
- [ ] **Terceiro aceita contrato:** LLM retorna `accept_contract` → truck status muda, rota criada com path mockado

### Guardrail Rejection — `test_guardrail_rejection_e2e.py`

- [ ] LLM retorna ação inválida (ex: `{"action": "fly_to_moon"}`) → guardrail rejeita, nenhum registro em `agent_decisions`
- [ ] LLM retorna `quantity_tons` negativa → guardrail Pydantic rejeita, nenhum pedido criado
- [ ] LLM retorna `quantity_tons` acima do estoque disponível → validação de negócio rejeita
- [ ] Caminhão com `degradation >= 0.95` + LLM retorna `accept_contract` → engine guardrail bloqueia viagem

### Multi-Tick Flow — `test_multi_tick_flow.py`

Cenário integrado que avança múltiplos ticks e verifica a evolução do mundo:

- [ ] Tick 1: seed state, estoques cheios, nenhum trigger dispara
- [ ] Ticks 2-5: estoques de lojas decrementam progressivamente
- [ ] Tick N: estoque de uma loja cruza o threshold, trigger dispara, agente cria pedido
- [ ] Verificar que o pedido aparece na tabela `pending_orders`
- [ ] Verificar que `age_ticks` incrementa a cada tick subsequente

---

## Estrutura de Arquivos

```
backend/tests/integration/
├── conftest.py                          # Fixtures (client, fake_llm, redis mock, etc.)
├── crud/                                # Feature 21
│   └── ...
├── simulation/
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures específicas (mock LLM, Valhalla, Redis)
│   ├── test_simulation_lifecycle.py
│   ├── test_physics_integration.py
│   ├── test_triggers_integration.py
│   ├── test_store_agent_e2e.py
│   ├── test_warehouse_agent_e2e.py
│   ├── test_factory_agent_e2e.py
│   ├── test_truck_agent_e2e.py
│   ├── test_guardrail_rejection_e2e.py
│   └── test_multi_tick_flow.py
└── database/
    ├── test_migrations.py               # Já existente
    └── test_seed.py                     # Já existente
```

---

## Mocking Strategy

### Camadas mockadas vs. reais

| Camada | Real ou Mock? | Motivo |
|---|---|---|
| PostgreSQL | **Real** (testcontainers) | Validar persistência e queries |
| SQLAlchemy / Alembic | **Real** | Validar ORM e migrations |
| FastAPI / Rotas | **Real** | Validar routing e serialization |
| Services | **Real** | Validar lógica de negócio |
| Repositories | **Real** | Validar queries SQL |
| Guardrails (Pydantic) | **Real** | Validar rejeição de decisões inválidas |
| OpenAI / LLM | **Mock** (FakeListChatModel) | Custo zero, determinismo |
| Redis Pub/Sub | **Mock** (AsyncMock) | Sem container extra |
| Valhalla HTTP | **Mock** (respx/httpx mock) | Sem container extra, rota fixa |

### Padrão de mock do LLM

```python
@pytest.fixture
def mock_store_llm():
    return fake_llm(json.dumps({
        "action": "order_replenishment",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 30.0,
            "from_warehouse_id": "warehouse-002"
        },
        "reasoning_summary": "Stock below reorder point, requesting from nearest warehouse"
    }))
```

O mock é injetado via `patch("src.agents.base.ChatOpenAI", return_value=mock_store_llm)`.
