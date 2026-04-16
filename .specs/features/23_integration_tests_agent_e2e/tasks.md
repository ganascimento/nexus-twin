# Tasks — Feature 23: Agent Wiring + E2E Integration Tests

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — convencoes, arquitetura
- `.specs/features/23_integration_tests_agent_e2e/specs.md` — cenarios e criterios
- `backend/src/simulation/engine.py` — `_evaluate_triggers`, `_dispatch_agent`, `run_tick`
- `backend/src/agents/base.py` — `build_agent_graph`, `_perceive_node`, `_fast_path_node`, `_decide_node`, `_act_node`
- `backend/src/agents/store_agent.py` — `StoreAgent.run_cycle`
- `backend/src/agents/warehouse_agent.py` — `WarehouseAgent.run_cycle`
- `backend/src/agents/factory_agent.py` — `FactoryAgent.run_cycle`
- `backend/src/agents/truck_agent.py` — `TruckAgent.run_cycle`
- `backend/src/simulation/events.py` — tipos de trigger
- `backend/tests/integration/simulation/conftest.py` — fixtures existentes
- `backend/tests/unit/agents/conftest.py` — helpers de mock do LLM

---

## Plano de Execucao

Feature com TDD obrigatorio. 2 fases.

---

### Fase 1 — Testes (aguardar aprovacao)

#### Tarefa 1.1 — Testes E2E dos agentes

**Arquivo:** `backend/tests/integration/simulation/test_agent_e2e.py`

Todos os testes usam:
- `seeded_simulation_client` fixture (truncate + seed + engine real + redis mock)
- `patch("src.agents.base.ChatOpenAI")` para injetar `FakeListChatModel`
- `await asyncio.sleep(1.0)` apos POST /tick para aguardar agents fire-and-forget
- `await async_session.rollback()` antes de queries de assertion
- `from sqlalchemy import text` para queries diretas

**Testes:**

1. `test_store_agent_creates_order_on_low_stock`:
   - UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento' (abaixo de reorder_point=15)
   - Commit
   - Patch ChatOpenAI com FakeListChatModel retornando order_replenishment
   - POST /tick + sleep
   - SELECT agent_decisions WHERE entity_id='store-001': assert action='order_replenishment'
   - SELECT pending_orders WHERE requester_id='store-001': assert exists

2. `test_warehouse_agent_creates_resupply_on_low_stock`:
   - UPDATE warehouse_stocks SET stock=10 WHERE warehouse_id='warehouse-001' AND material_id='vergalhao' (min_stock=100)
   - Commit + Patch + tick + sleep
   - SELECT agent_decisions WHERE entity_id='warehouse-001'
   - SELECT pending_orders WHERE requester_id='warehouse-001'

3. `test_factory_agent_starts_production`:
   - UPDATE factory_products SET stock=50, production_rate_current=0 WHERE factory_id='factory-003' AND material_id='cimento' (stock_max=750, 50/750 < 0.3)
   - Commit + Patch + tick + sleep
   - SELECT agent_decisions WHERE entity_id='factory-003': assert action='start_production'

4. `test_guardrail_rejects_invalid_action`:
   - UPDATE store_stocks SET stock=1.0 (trigger fires)
   - Patch LLM com resposta invalida: `{"action": "fly_to_moon"}`
   - POST /tick + sleep
   - SELECT agent_decisions: assert NENHUM registro para store-001
   - SELECT pending_orders: assert NENHUM novo pedido

5. `test_multi_tick_triggers_store_agent`:
   - Nao manipular dados (seed default)
   - Avancar ticks ate estoque cruzar threshold (store-001/tijolos: stock=1.5, demand_rate=0.5, reorder_point=1.0 → ~2-3 ticks)
   - Patch LLM retornando order_replenishment
   - Verificar que agent_decisions tem registro em algum tick
   - Verificar pending_orders criado

6. `test_store_fast_path_emergency_order`:
   - UPDATE store_stocks SET stock=0.1 WHERE store_id='store-001' AND material_id='cimento' (< 10% do reorder_point=15, zona critica)
   - Commit + tick + sleep
   - SELECT agent_decisions: assert action correto (emergency order)
   - LLM NAO deve ter sido chamado (verificar que FakeListChatModel nao consumiu resposta)

7. `test_tick_resilient_to_agent_errors`:
   - UPDATE store_stocks SET stock=1.0 (trigger fires)
   - Patch ChatOpenAI para lancar Exception
   - POST /tick
   - Assert 200 — engine nao crasha (agents sao fire-and-forget)
   - Physics still applied (stock decremented)

8. `test_redis_receives_agent_decision`:
   - Setup que dispara agente (stock baixo)
   - Patch LLM + tick + sleep
   - Assert mock_redis.publish foi chamado com 'nexus:agent_decisions'

**Observacoes sobre sleep:**
- Agentes rodam via `asyncio.create_task` (fire-and-forget)
- O tick retorna ANTES dos agentes completarem
- `await asyncio.sleep(1.0)` da tempo para o agente completar o ciclo
- Se flaky, aumentar para 2.0s

---

### Fase 2 — Implementacao (apos aprovacao dos testes)

#### Tarefa 2.1 — Wiring do engine

**Arquivo:** `backend/src/simulation/engine.py`

Modificar `_evaluate_triggers` e `_dispatch_agent` para conectar os agentes reais:

1. Criar metodo `_make_agent_callable(entity_type, entity_id)` que retorna uma coroutine:
   ```python
   async def _make_agent_callable(self, entity_type, entity_id):
       async def _run(event):
           async with self._session_factory() as session:
               agent_class = AGENT_MAP[entity_type]
               agent = agent_class(entity_id, session, self._publisher_redis_client)
               await agent.run_cycle(event)
       return _run
   ```

2. Definir `AGENT_MAP`:
   ```python
   from src.agents.store_agent import StoreAgent
   from src.agents.warehouse_agent import WarehouseAgent
   from src.agents.factory_agent import FactoryAgent
   from src.agents.truck_agent import TruckAgent
   
   AGENT_MAP = {
       "store": StoreAgent,
       "warehouse": WarehouseAgent,
       "factory": FactoryAgent,
       "truck": TruckAgent,
   }
   ```

3. Substituir `(None, event)` por `(self._make_agent_callable(entity_type, entity_id), event)` em todos os triggers

4. Manter error handling em `_dispatch_agent` — se o agente crashar, logar e continuar:
   ```python
   async def _dispatch_agent(self, agent_fn, event):
       async with self._semaphore:
           if agent_fn is not None:
               try:
                   await agent_fn(event)
               except Exception as exc:
                   logger.error("Agent dispatch failed: {}", exc)
   ```

#### Tarefa 2.2 — Ajustes nos agentes (se necessario)

Verificar que cada agente funciona quando chamado pelo engine:
- `run_cycle` aceita um `SimulationEvent` como parametro
- Session e publisher sao passados no construtor
- Perceive node consegue ler dados do banco com a session fornecida

---

## Observacoes

- **LLM sempre mockado** — `FakeListChatModel` ou patch no `ChatOpenAI`
- **Agent tools podem falhar** — tools fazem queries ao banco e chamadas HTTP. Para E2E, tools devem funcionar contra o banco real. Se falharem, mockar tools individualmente.
- **Fire-and-forget timing** — se testes forem flaky por timing, usar mecanismo de polling (loop ate agent_decisions aparecer, com timeout)
- **Error isolation** — cada teste e independente (truncate + re-seed)
