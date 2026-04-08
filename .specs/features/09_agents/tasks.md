# Tasks — Feature 09: Agents

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — arquitetura do MAS (§4.2), ciclo perceive → decide → act, perfis de caminhão (proprietario/terceiro), regras de fast path, TDD (§9), convenções (§8)
- `.specs/features/09_agents/specs.md` — critérios de aceitação desta feature
- `backend/src/agents/base.py` — `AgentState`, `WorldStateSlice`, `build_agent_graph()`, `perceive_node`, `fast_path_node`, `has_tool_calls()`
- `backend/src/agents/master_agent.py` — `MasterAgentState`, `run_master_cycle_full()` — para entender como `agent_factory` é injetado
- `backend/src/simulation/engine.py` — para entender como `AgentTrigger` é definido e passado aos agentes
- `backend/src/services/trigger_evaluation.py` — definição de `AgentTrigger` (campos: `entity_id`, `entity_type`, `trigger_event`, `current_tick`)
- `backend/src/repositories/` — `FactoryRepository`, `WarehouseRepository`, `StoreRepository`, `TruckRepository`, `EventRepository`, `OrderRepository` — métodos disponíveis para montar o `WorldStateSlice`
- `.specs/design.md §1` — schema das tabelas `factory_products`, `warehouse_stocks`, `store_stocks`, `trucks`, `routes`, `pending_orders`, `events`

Não leia specs de outras features. Não escreva nenhum código de guardrail (feature 10) nem de tools (feature 11).

---

## Plano de Execução

**Fase 1 (TDD) — Grupo 1:** escrever todos os testes antes de qualquer implementação. Parar e aguardar aprovação.

**Fase 2 (Implementação) — Grupos 2–4 podem rodar em paralelo** após aprovação dos testes.

**Grupo 5** é sequencial — roda após os Grupos 2–4 para validar a integração e atualizar o state.

---

### Grupo 1 — Testes (um agente — FASE 1: TDD) ⛔ PARAR AQUI

**Tarefa:** Escrever todos os testes unitários dos quatro agentes concretos. Não escrever nenhum código de implementação.

**Estrutura de pastas dos testes** (espelha `backend/src/agents/`):

```
backend/tests/unit/agents/
├── __init__.py
├── test_factory_agent.py
├── test_warehouse_agent.py
├── test_store_agent.py
└── test_truck_agent.py
```

Criar `backend/tests/unit/agents/__init__.py` se não existir.

**Fixtures compartilhadas** — criar ou verificar `backend/tests/unit/agents/conftest.py`:

- `mock_db_session` — `AsyncMock` de `AsyncSession`
- `mock_publisher` — `MagicMock` com método `publish_decision` assíncrono
- `mock_decision_repo` — `AsyncMock` de `AgentDecisionRepository` com `get_recent_by_entity` retornando `[]` e `create` retornando `None`
- `stub_guardrail(action)` — classe Pydantic mínima que aceita qualquer `action` e `payload` sem validar (para isolar o guardrail da feature 10)
- `fake_llm(response_json)` — `FakeListChatModel` configurado para retornar a string JSON fornecida como `AIMessage`

**`test_factory_agent.py`** — escrever os seguintes testes:

1. `test_run_cycle_completes_full_path` — `FactoryAgent.run_cycle()` com `FakeListChatModel` retornando `{"action": "start_production", "payload": {}}` completa o ciclo e `AgentDecisionRepository.create()` é chamado uma vez com `action="start_production"` e `entity_id` correto
2. `test_build_world_state_slice_includes_factory_products` — `_build_world_state_slice()` com mock do `FactoryRepository.get_by_id()` retornando factory com `products=[{"material_id": "tijolos", "stock": 10}]` — `slice["entity"]` contém `products`
3. `test_build_world_state_slice_includes_partner_warehouses` — `_build_world_state_slice()` inclui armazéns parceiros em `slice["related_entities"]`
4. `test_build_world_state_slice_filters_active_events` — quando há eventos com `entity_id` diferente, apenas o evento com `entity_id == self.entity_id` aparece em `slice["active_events"]`

**`test_warehouse_agent.py`** — escrever os seguintes testes:

1. `test_run_cycle_completes_full_path` — mesmo padrão do factory: `WarehouseAgent.run_cycle()` com fake LLM, `create()` chamado com `entity_type="warehouse"`
2. `test_build_world_state_slice_includes_warehouse_stocks` — `slice["entity"]` contém `stocks`
3. `test_build_world_state_slice_limits_related_entities` — quando o mock retorna 15 entidades relacionadas, `slice["related_entities"]` tem no máximo 10
4. `test_build_world_state_slice_filters_pending_orders_by_target` — apenas pedidos com `target_id == entity_id` aparecem em `slice["pending_orders"]`

**`test_store_agent.py`** — escrever os seguintes testes:

1. `test_run_cycle_completes_full_path` — `StoreAgent.run_cycle()` com fake LLM, `create()` chamado com `entity_type="store"`
2. `test_build_world_state_slice_includes_store_stocks` — `slice["entity"]` contém `stocks` com `demand_rate` e `reorder_point`
3. `test_build_world_state_slice_filters_pending_orders_by_requester` — apenas pedidos com `requester_id == entity_id`

**`test_truck_agent.py`** — escrever os seguintes testes:

1. `test_run_cycle_completes_full_path` — `TruckAgent.run_cycle()` com fake LLM, `create()` chamado com `entity_type="truck"`
2. `test_build_world_state_slice_includes_truck_type` — `slice["entity"]` contém `truck_type`
3. `test_build_world_state_slice_includes_active_route` — quando caminhão tem `active_route_id`, `slice["related_entities"]` inclui a rota
4. `test_fast_path_maintenance_when_degradation_critical` — `TruckAgent.run_cycle()` com `degradation=0.95` no estado: `fast_path_node` retorna `fast_path_taken=True` e `action="request_maintenance"`, LLM não é chamado (verificar que `FakeListChatModel.invoke` não foi invocado)
5. `test_proprietario_does_not_block_on_fast_path` — `TruckAgent` com `truck_type="proprietario"` e `degradation=0.5`: ciclo chega ao nó `decide` (LLM é chamado)

**⛔ Parar após criar os testes. Não escrever nenhum código de implementação. Aguardar aprovação do usuário.**

---

### Grupo 2 — FactoryAgent e WarehouseAgent (um agente — FASE 2)

**Tarefa:** Implementar `FactoryAgent` e `WarehouseAgent` após aprovação dos testes.

1. Implementar `backend/src/agents/factory_agent.py`:
   - Classe `FactoryAgent` com `__init__(self, entity_id: str, db_session: AsyncSession, publisher)`
   - Método privado `async _build_world_state_slice(current_tick: int) -> WorldStateSlice`:
     - Chama `FactoryRepository(db_session).get_by_id(entity_id)` — serializa para dict incluindo `factory_products`
     - Chama `FactoryRepository(db_session).get_partner_warehouses(entity_id)` — lista de armazéns parceiros (máx 10), serializa para dicts
     - Chama `EventRepository(db_session).get_active_for_entity("factory", entity_id)` — serializa para lista de dicts
     - Chama `OrderRepository(db_session).get_pending_for_target("factory", entity_id)` — serializa para lista de dicts
     - Retorna `WorldStateSlice(entity=..., related_entities=..., active_events=..., pending_orders=...)`
   - Método `async run_cycle(trigger) -> None`:
     - Importa `FactoryDecision` de `src.guardrails.factory` (stub por ora)
     - Chama `build_agent_graph("factory", tools=[], decision_schema_map={"factory": FactoryDecision}, db_session=self.db_session, publisher_instance=self.publisher)` — conforme assinatura de `base.py`
     - Monta `AgentState` inicial: `entity_id`, `entity_type="factory"`, `trigger_event=trigger.trigger_event`, `current_tick=trigger.current_tick`, `world_state=await self._build_world_state_slice(trigger.current_tick)`, `messages=[]`, `decision_history=[]`, `decision=None`, `fast_path_taken=False`, `error=None`
     - Chama `await graph.ainvoke(initial_state)`

2. Implementar `backend/src/agents/warehouse_agent.py` com a mesma estrutura:
   - `_build_world_state_slice()`: `WarehouseRepository.get_by_id()` (inclui `warehouse_stocks`), fábricas parceiras via `FactoryRepository.list_partner_for_warehouse(entity_id)`, pedidos pendentes onde `target_id == entity_id` via `OrderRepository`, eventos ativos via `EventRepository` — limitar `related_entities` a 10
   - `run_cycle()`: importa `WarehouseDecision` de `src.guardrails.warehouse`, `entity_type="warehouse"`

---

### Grupo 3 — StoreAgent e TruckAgent (um agente — FASE 2)

**Tarefa:** Implementar `StoreAgent` e `TruckAgent` após aprovação dos testes.

1. Implementar `backend/src/agents/store_agent.py`:
   - `_build_world_state_slice()`:
     - `StoreRepository.get_by_id(entity_id)` — inclui `store_stocks` com `demand_rate` e `reorder_point` por material
     - Armazéns regionais via `WarehouseRepository.list_by_region(store.region)` — máx 10
     - Pedidos pendentes onde `requester_id == entity_id` via `OrderRepository`
     - Eventos ativos via `EventRepository`
   - `run_cycle()`: `entity_type="store"`, importa `StoreDecision` de `src.guardrails.store`

2. Implementar `backend/src/agents/truck_agent.py`:
   - `_build_world_state_slice()`:
     - `TruckRepository.get_by_id(entity_id)` — dict com `truck_type`, `degradation`, `cargo`, `status`
     - Se `truck.active_route_id` não é `None`: `RouteRepository.get_by_id(truck.active_route_id)` e adiciona em `related_entities`
     - Se `truck.cargo` contém `origin` e `destination`: carrega entidades de origem e destino e adiciona em `related_entities`
     - Eventos ativos via `EventRepository.get_active_for_entity("truck", entity_id)`
   - `run_cycle()`: `entity_type="truck"`, importa `TruckDecision` de `src.guardrails.truck`

---

### Grupo 4 — System Prompts (um agente — FASE 2)

**Tarefa:** Substituir os stubs dos prompts por prompts reais com instruções completas para cada tipo de agente.

1. Reescrever `backend/src/agents/prompts/factory.md`:
   - **Identidade:** agente responsável pela Fábrica `{entity_id}`, objetivo de maximizar produção eficiente e garantir abastecimento dos armazéns parceiros
   - **Estado atual:** placeholder `{world_state_summary}` (serialização do `WorldStateSlice`)
   - **Histórico:** placeholder `{decision_history}`
   - **Gatilho atual:** placeholder `{trigger_event}`
   - **Regras de decisão:**
     - `stock_projection`: se estoque de algum produto está abaixo de 50% da capacidade → `start_production`; acima de 90% → `hold`
     - `resupply_requested`: avaliar estoque disponível; se há estoque suficiente → `send_stock` com `quantity_tons` e `to_warehouse`; se insuficiente → iniciar produção primeiro
     - `machine_breakdown`: `stop_production` e registrar no payload o produto afetado
   - **Formato de resposta:** JSON com `action`, `payload` e `reasoning_summary`; lista de ações válidas com exemplos de payload

2. Reescrever `backend/src/agents/prompts/warehouse.md`:
   - **Identidade:** agente do Armazém `{entity_id}`, responsável por redistribuição regional
   - **Regras de decisão:**
     - `stock_projection`: se projeção indica ruptura antes da reposição → `request_resupply` para a fábrica parceira de maior prioridade com `quantity_tons` e `from_factory`
     - `order_received`: verificar estoque disponível; se suficiente → `confirm_order` com `eta_ticks`; se insuficiente → `reject_order` com `reason`
     - `resupply_delivered`: confirmar recebimento e atualizar pedidos pendentes às lojas — `confirm_order` para pedidos em espera
   - **Formato de resposta:** JSON com `action`, `payload`, `reasoning_summary`

3. Reescrever `backend/src/agents/prompts/store.md`:
   - **Identidade:** agente da Loja `{entity_id}`, responsável por manter estoque para atender demanda
   - **Regras de decisão:**
     - `stock_projection`: calcular quantidade para cobrir `demand_rate * lead_time_ticks * 1.5` acima de `reorder_point`; `order_replenishment` com `quantity_tons`, `material_id` e `from_warehouse`
     - `demand_spike`: aumentar pedido de reposição para cobrir pico; ajustar `quantity_tons`
   - **Formato de resposta:** JSON com `action`, `payload`, `reasoning_summary`

4. Reescrever `backend/src/agents/prompts/truck.md`:
   - **Identidade:** agente do Caminhão `{entity_id}`, perfil: `{truck_type}`
   - **Seção PROPRIETARIO:** executa ordens diretas da fábrica vinculada sem autonomia para recusar; gatilhos `new_order`, `route_blocked`, `truck_arrived`, `truck_breakdown`; em `route_blocked` → `reroute`; em `truck_breakdown` → `request_maintenance`
   - **Seção TERCEIRO:** agente self-interested; gatilhos `contract_proposal`, `route_blocked`, `truck_arrived`, `truck_breakdown`; critérios para `accept_contract`: aproveitamento de carga ≥ 80%, degradação < 70%, risco de rota aceitável, `age_ticks` alto eleva prioridade; motivo de recusa obrigatório em `refuse_contract`
   - **Regra absoluta (ambos perfis):** se `degradation >= 0.95` → `request_maintenance` independentemente do gatilho
   - **Formato de resposta:** JSON com `action`, `payload`, `reasoning_summary`

---

### Grupo 5 — Integração e Validação (sequencial, após Grupos 2–4)

**Tarefa:** Conectar os agentes ao `MasterAgent`, atualizar `__init__.py` e rodar os testes.

1. Atualizar `backend/src/agents/__init__.py`:

   ```python
   from src.agents.factory_agent import FactoryAgent
   from src.agents.warehouse_agent import WarehouseAgent
   from src.agents.store_agent import StoreAgent
   from src.agents.truck_agent import TruckAgent
   ```

2. Verificar se `run_master_cycle_full()` em `master_agent.py` pode receber uma função `agent_factory` que retorna instâncias dos quatro agentes por `entity_type`. Se necessário, adicionar um exemplo de `agent_factory` em `__init__.py` — mas não modificar a lógica do `MasterAgent` (feature 08).

3. Rodar os testes: `pytest backend/tests/unit/agents/ -v`
   - Corrigir qualquer falha antes de avançar
   - Todos os testes devem passar com `PASSED` — sem `ERROR` nem `FAILED`

4. Atualizar `state.md`: setar o status da feature `09` para `done`.

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes em `backend/tests/unit/agents/` passam com `pytest`.
`state.md` atualizado com feature 09 como `done`.
