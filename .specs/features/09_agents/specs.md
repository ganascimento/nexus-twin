# Feature 09 — Agents

## Objetivo

Implementa os quatro agentes concretos do sistema multi-agente (MAS): `FactoryAgent`, `WarehouseAgent`, `StoreAgent` e `TruckAgent`. Cada agente é uma classe Python com um método `run_cycle(trigger)` que monta seu `WorldStateSlice`, constrói o estado inicial do `AgentState` e executa o grafo LangGraph compilado por `build_agent_graph()` (feature 08).

Esta feature também entrega os system prompts reais em `backend/src/agents/prompts/` — substituindo os stubs da feature 08 por prompts com instruções completas de identidade, formato de resposta e regras de decisão por tipo de agente.

Sem esta feature, o engine (feature 07) e o MasterAgent (feature 08) não têm agentes reais para disparar — o loop de ticks roda, mas nenhuma decisão inteligente é tomada.

---

## Critérios de Aceitação

### Backend — FactoryAgent

- [ ] `backend/src/agents/factory_agent.py` exporta `FactoryAgent` com construtor `__init__(self, entity_id: str, db_session: AsyncSession, publisher)`
- [ ] `FactoryAgent.run_cycle(trigger: AgentTrigger) -> None` monta `WorldStateSlice` com: entidade fábrica (com `factory_products`), armazéns parceiros (`factory_partner_warehouses`), eventos ativos para a fábrica, pedidos pendentes com `target_id == entity_id`
- [ ] `FactoryAgent` usa `build_agent_graph("factory", tools=[], decision_schema_map={"factory": FactoryDecision})` — onde `FactoryDecision` é importado de `src.guardrails.factory`
- [ ] Gatilhos reconhecidos pelo `FactoryAgent`: `stock_projection`, `resupply_requested`, `machine_breakdown`
- [ ] Ações esperadas na decisão: `start_production`, `stop_production`, `send_stock`, `hold`

### Backend — WarehouseAgent

- [ ] `backend/src/agents/warehouse_agent.py` exporta `WarehouseAgent` com construtor `__init__(self, entity_id: str, db_session: AsyncSession, publisher)`
- [ ] `WarehouseAgent.run_cycle(trigger: AgentTrigger) -> None` monta `WorldStateSlice` com: entidade armazém (com `warehouse_stocks`), fábricas parceiras, lojas da região com pedidos pendentes ao armazém, eventos ativos para o armazém
- [ ] `WarehouseAgent` usa `build_agent_graph("warehouse", tools=[], decision_schema_map={"warehouse": WarehouseDecision})`
- [ ] Gatilhos reconhecidos: `stock_projection`, `order_received`, `resupply_delivered`
- [ ] Ações esperadas: `request_resupply`, `confirm_order`, `reject_order`, `hold`

### Backend — StoreAgent

- [ ] `backend/src/agents/store_agent.py` exporta `StoreAgent` com construtor `__init__(self, entity_id: str, db_session: AsyncSession, publisher)`
- [ ] `StoreAgent.run_cycle(trigger: AgentTrigger) -> None` monta `WorldStateSlice` com: entidade loja (com `store_stocks` e `demand_rate`/`reorder_point` por material), armazéns regionais disponíveis, pedidos pendentes com `requester_id == entity_id`, eventos ativos para a loja
- [ ] `StoreAgent` usa `build_agent_graph("store", tools=[], decision_schema_map={"store": StoreDecision})`
- [ ] Gatilhos reconhecidos: `stock_projection`, `demand_spike`
- [ ] Ações esperadas: `order_replenishment`, `hold`

### Backend — TruckAgent

- [ ] `backend/src/agents/truck_agent.py` exporta `TruckAgent` com construtor `__init__(self, entity_id: str, db_session: AsyncSession, publisher)`
- [ ] `TruckAgent.run_cycle(trigger: AgentTrigger) -> None` monta `WorldStateSlice` com: entidade caminhão (incluindo `degradation`, `cargo`, `truck_type`), rota ativa (se houver), entidade de origem e destino do cargo, eventos ativos para o caminhão
- [ ] `TruckAgent` usa `build_agent_graph("truck", tools=[], decision_schema_map={"truck": TruckDecision})`
- [ ] Gatilhos reconhecidos: `contract_proposal` (terceiro), `new_order` (proprietário), `route_blocked`, `truck_arrived`, `truck_breakdown`
- [ ] Ações esperadas: `accept_contract`, `refuse_contract`, `request_maintenance`, `reroute`
- [ ] `TruckAgent` inclui `truck_type` no `WorldStateSlice["entity"]` para que o prompt diferencie o comportamento de `proprietario` vs `terceiro`

### Backend — Construção do WorldStateSlice

- [ ] Cada agente concreto tem método privado `_build_world_state_slice() -> WorldStateSlice` que usa repositories para montar o slice sem carregar o `WorldState` completo
- [ ] `WorldStateSlice["entity"]` contém apenas os campos da entidade dona do agente
- [ ] `WorldStateSlice["related_entities"]` contém no máximo 10 entidades relacionadas (armazéns parceiros, lojas da região, etc.)
- [ ] `WorldStateSlice["active_events"]` filtra apenas eventos com `entity_id == self.entity_id` e `status == "active"`
- [ ] `WorldStateSlice["pending_orders"]` filtra pedidos relevantes para aquela entidade (como `target_id` ou `requester_id`)

### Backend — Sistema de Prompts

- [ ] `backend/src/agents/prompts/factory.md` contém: identidade do agente fábrica, instruções de gatilhos (`stock_projection`, `resupply_requested`, `machine_breakdown`), regras de decisão (quando produzir, quando parar, quando despachar estoque), formato de resposta JSON com campos `action`, `payload` e `reasoning_summary`
- [ ] `backend/src/agents/prompts/warehouse.md` contém: identidade do armazém, gatilhos (`stock_projection`, `order_received`, `resupply_delivered`), regras de confirmação/rejeição de pedidos e de solicitação de reposição às fábricas, formato de resposta JSON
- [ ] `backend/src/agents/prompts/store.md` contém: identidade da loja, gatilhos (`stock_projection`, `demand_spike`), regras de quando e quanto pedir baseadas em `reorder_point` e `demand_rate`, formato de resposta JSON
- [ ] `backend/src/agents/prompts/truck.md` contém: identidade do caminhão, seção de instruções separada por perfil (`proprietario` executa ordens diretas sem autonomia para recusar; `terceiro` avalia risco de rota, distância, aproveitamento de carga ≥ 80%, `degradation` atual, prioridade por `age_ticks`), gatilhos reconhecidos e ações correspondentes, formato de resposta JSON
- [ ] Todos os prompts usam os placeholders `{entity_id}`, `{trigger_event}`, `{world_state_summary}` e `{decision_history}` — substituídos no `perceive_node` de `base.py`

### Backend — Integração

- [ ] `backend/src/agents/__init__.py` exporta `FactoryAgent`, `WarehouseAgent`, `StoreAgent`, `TruckAgent`
- [ ] `run_cycle()` é `async` e pode ser executado via `asyncio.create_task()` sem bloquear o tick

### Testes

- [ ] `FactoryAgent.run_cycle()` com `FakeListChatModel` completa o ciclo `perceive → fast_path → decide → act` e chama `AgentDecisionRepository.create()` (mock)
- [ ] `WarehouseAgent.run_cycle()` com `FakeListChatModel` completa o ciclo e chama `AgentDecisionRepository.create()` (mock)
- [ ] `StoreAgent.run_cycle()` com `FakeListChatModel` completa o ciclo e chama `AgentDecisionRepository.create()` (mock)
- [ ] `TruckAgent.run_cycle()` com `FakeListChatModel` completa o ciclo e chama `AgentDecisionRepository.create()` (mock)
- [ ] `TruckAgent._build_world_state_slice()` inclui `truck_type` no slice `entity` (testado com mock do repository)
- [ ] `FactoryAgent._build_world_state_slice()` inclui `factory_products` e armazéns parceiros no slice (testado com mock do repository)
- [ ] `WarehouseAgent._build_world_state_slice()` limita `related_entities` a no máximo 10 entidades
- [ ] Para `truck_type = "terceiro"` com `degradation >= 0.95`: `fast_path_node` retorna `fast_path_taken=True` com `action = "request_maintenance"` sem chamar LLM
- [ ] Cada teste de agente usa `AsyncSession` mockada — sem banco real

---

## Fora do Escopo

- Guardrail Pydantic schemas (`FactoryDecision`, `WarehouseDecision`, `StoreDecision`, `TruckDecision`) — feature 10; nesta feature os agentes importam de `src.guardrails.*` mas os schemas são stubs até a feature 10
- Agent tools com decorator `@tool` (`weather`, `route_risk`, `sales_history`) — feature 11; os agentes são construídos com `tools=[]` nesta feature
- Exposição dos agentes via API REST ou WebSocket — features 13 e 14
- Lógica interna do `TriggerEvaluationService` — feature 07 (já implementado)
- Lógica interna de `ChaosService.inject_autonomous_event()` — feature 12
- `build_agent_graph()` e `AgentState` — feature 08 (já implementado)
- `MasterAgent` e grafo supervisor — feature 08 (já implementado)
