# Tasks — Feature 22: Integration Tests Simulation

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — estrutura, convencoes, TDD
- `.specs/features/22_integration_tests_simulation/specs.md` — criterios de aceitacao
- `.specs/design.md` S8 — schema do grafo dos agentes, responsabilidade de cada no
- `.specs/design.md` S9 — guardrails Pydantic, hierarquia de validacao
- `.specs/prd.md` S2 — definicao de tick, separacao physics vs. agent cycle
- `.specs/prd.md` S5 — logica de decisao de cada ator
- `backend/tests/conftest.py` — fixtures existentes
- `backend/tests/unit/agents/conftest.py` — fake_llm e helpers de mock de agente
- `backend/src/simulation/engine.py` — loop de ticks, apply_physics, evaluate_triggers
- `backend/src/agents/base.py` — build_agent_graph, perceive/decide/act nodes
- `backend/src/guardrails/*.py` — schemas de decisao por agente

---

## Plano de Execucao

Feature com TDD **invertido** (os testes SAO o entregavel). 4 grupos sequenciais.

---

### Grupo 1 — Infraestrutura de Teste

#### Tarefa 1.1 — Conftest de simulacao

**Arquivo:** `backend/tests/integration/simulation/conftest.py`

Criar fixtures especializadas para testes de simulacao:

1. Fixture `fake_llm_factory` — factory function que aceita response JSON e retorna `FakeListChatModel`

2. Fixture `mock_redis` — `AsyncMock()` com:
   - `publish` — captura chamadas para assertions
   - `pubsub` — retorna AsyncMock (para subscriber)
   - `from_url` classmethod mocado

3. Fixture `mock_valhalla` — mock de `httpx.AsyncClient.post` que retorna rota fixa:
   ```python
   {
       "trip": {
           "legs": [{"shape": "encoded_polyline"}],
           "summary": {"length": 100.0, "time": 7200}
       }
   }
   ```
   Path fixo: `[[-47.06, -22.91], [-46.90, -23.10], [-46.63, -23.55]]`

4. Fixture `simulation_client` — httpx AsyncClient com overrides:
   - `get_db` → async_session do testcontainer
   - Redis → mock_redis
   - Patch `ChatOpenAI` → fake_llm

5. Fixture `seeded_world` — seed + retorna session pronta para manipulacao

6. Helper `advance_n_ticks(client, n)` — chama POST /simulation/tick N vezes

7. Criar `backend/tests/integration/simulation/__init__.py`

---

### Grupo 2 — Simulation Lifecycle + Physics (paralelizaveis)

#### Subagente 2A — Simulation Lifecycle

**Arquivo:** `backend/tests/integration/simulation/test_simulation_lifecycle.py`

Testes (usam `simulation_client`):

1. `test_start_simulation` — POST /start, verifica 200
2. `test_status_after_start` — POST /start + GET /status, verifica `status=running`
3. `test_stop_simulation` — POST /start + /stop, verifica 200
4. `test_status_after_stop` — POST /start + /stop + GET /status, verifica `status=stopped`
5. `test_manual_tick_when_stopped` — POST /tick, verifica current_tick incrementa
6. `test_manual_tick_when_running_returns_409` — POST /start + POST /tick, verifica 409
7. `test_speed_update` — PATCH /speed com 15, GET /status confirma
8. `test_speed_minimum_enforced` — PATCH /speed com 5, GET /status confirma 10 (minimo)

#### Subagente 2B — Physics Integration

**Arquivo:** `backend/tests/integration/simulation/test_physics_integration.py`

Testes (usam `simulation_client` + `seeded_world`):

1. `test_store_stock_decrements_by_demand_rate`:
   - Ler estoque da store-001 antes do tick
   - POST /tick
   - SELECT store_stocks WHERE store_id='store-001' AND material_id='cimento'
   - Assert: stock_after = stock_before - demand_rate

2. `test_factory_production_increments_stock`:
   - UPDATE factory_products SET production_rate_current = production_rate_max WHERE factory_id='factory-003'
   - POST /tick
   - SELECT: assert stock_after = stock_before + production_rate_max (ou stock_max se atingiu teto)

3. `test_factory_production_caps_at_stock_max`:
   - SET stock = stock_max - 1, production_rate_current = 5
   - POST /tick
   - Assert: stock_after <= stock_max

4. `test_pending_orders_age_increments`:
   - INSERT pending_order com age_ticks=0
   - POST /tick
   - SELECT: assert age_ticks = 1

5. `test_truck_in_transit_completes_route`:
   - INSERT truck com status=in_transit, route com eta_ticks=1
   - POST /tick
   - SELECT truck: assert status=idle, route: assert status=completed

6. `test_truck_position_interpolates`:
   - INSERT truck in_transit com route (path com 3 pontos, eta_ticks=3)
   - POST /tick
   - SELECT truck: assert current_lat/lng mudou em direcao ao destino

---

### Grupo 3 — Triggers + Agent E2E (paralelizaveis)

#### Subagente 3A — Triggers

**Arquivo:** `backend/tests/integration/simulation/test_triggers_integration.py`

Testes (usam `simulation_client` + `seeded_world`):

1. `test_store_trigger_fires_when_stock_low`:
   - UPDATE store_stocks SET stock = reorder_point * 0.5 (forca trigger)
   - POST /tick (com LLM mockado retornando hold)
   - Verificar que o agente foi acionado (agent_decisions registrada)

2. `test_store_trigger_does_not_fire_when_stock_comfortable`:
   - Manter estoque confortavel (seed default)
   - POST /tick
   - Verificar que NAO ha agent_decisions para stores

3. `test_warehouse_trigger_fires_when_below_min_stock`:
   - UPDATE warehouse_stocks SET stock = min_stock * 0.8
   - POST /tick
   - Verificar trigger disparado

4. `test_factory_trigger_fires_when_stock_low_and_idle`:
   - UPDATE factory_products SET stock = stock_max * 0.2, production_rate_current = 0
   - POST /tick
   - Verificar trigger disparado

#### Subagente 3B — Store Agent E2E

**Arquivo:** `backend/tests/integration/simulation/test_store_agent_e2e.py`

Setup: seed + forcar estoque baixo.

LLM mockado retorna: `order_replenishment` para cimento de warehouse-002.

1. `test_store_agent_creates_pending_order`:
   - Forcar estoque baixo
   - POST /tick (agente dispara)
   - SELECT pending_orders WHERE requester_id='store-001': assert existe com material_id='cimento'

2. `test_store_agent_decision_persisted`:
   - Mesmo setup
   - SELECT agent_decisions WHERE entity_id='store-001': assert action='order_replenishment'

3. `test_store_agent_decision_published_to_redis`:
   - Mesmo setup
   - Assert mock_redis.publish foi chamado com canal 'nexus:agent_decisions'

#### Subagente 3C — Warehouse Agent E2E

**Arquivo:** `backend/tests/integration/simulation/test_warehouse_agent_e2e.py`

LLM mockado retorna: `request_resupply` de factory-002.

1. `test_warehouse_agent_creates_resupply_order`
2. `test_warehouse_agent_decision_persisted`

#### Subagente 3D — Factory Agent E2E

**Arquivo:** `backend/tests/integration/simulation/test_factory_agent_e2e.py`

LLM mockado retorna: `start_production`.

1. `test_factory_agent_updates_production_rate`
2. `test_factory_agent_decision_persisted`

#### Subagente 3E — Truck Agent E2E

**Arquivo:** `backend/tests/integration/simulation/test_truck_agent_e2e.py`

Dois cenarios com LLM mockado:

1. `test_proprietario_accepts_order` — LLM retorna accept_contract
2. `test_terceiro_refuses_contract` — LLM retorna refuse_contract com motivo
3. `test_terceiro_accepts_contract` — LLM retorna accept_contract

---

### Grupo 4 — Guardrails + Multi-Tick

#### Subagente 4A — Guardrail Rejection

**Arquivo:** `backend/tests/integration/simulation/test_guardrail_rejection_e2e.py`

1. `test_invalid_action_rejected`:
   - LLM retorna `{"action": "fly_to_moon", ...}`
   - POST /tick
   - Assert: NENHUM agent_decisions criado, error logado

2. `test_negative_quantity_rejected`:
   - LLM retorna quantity_tons = -10
   - Assert: nenhum pending_order criado

3. `test_degradation_guardrail_blocks_trip`:
   - UPDATE truck SET degradation = 0.96
   - LLM retorna accept_contract
   - Assert: truck permanece idle, viagem bloqueada

#### Subagente 4B — Multi-Tick Flow

**Arquivo:** `backend/tests/integration/simulation/test_multi_tick_flow.py`

Cenario completo: avanca multiplos ticks e observa evolucao do mundo.

1. `test_stock_depletes_over_ticks`:
   - Avancar 5 ticks
   - Assert: estoque de lojas diminuiu progressivamente

2. `test_trigger_fires_after_stock_depletion`:
   - Avancar N ticks ate estoque cruzar threshold
   - Assert: pending_order criado no tick correto

3. `test_world_state_published_each_tick`:
   - Avancar 3 ticks
   - Assert: mock_redis.publish chamado 3x com canal 'nexus:world_state'

---

## Observacoes

- **LLM sempre mockado** — nunca chamar OpenAI real em testes
- **Redis sempre mockado** — publisher captura para assertions
- **Valhalla mockado** — rota fixa para testes de truck
- **PostgreSQL real** — unico servico com container real
- **Cada teste independente** — rollback automatico entre testes
- **Patch no nivel correto** — `patch("src.agents.base.ChatOpenAI", ...)` para interceptar o LLM
- **Testes e2e de agentes sao assincronos** — agentes rodam via asyncio.create_task, usar `await asyncio.sleep(0.1)` ou `await asyncio.gather()` para aguardar conclusao
