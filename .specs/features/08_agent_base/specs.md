# Feature 08 — Agent Base

## Objetivo

Implementa a infraestrutura base do sistema multi-agente (MAS). Entrega os TypedDicts `AgentState`, `WorldStateSlice`, `DecisionMemory` e `AgentDecision` que definem o contrato de interface entre os nós do `StateGraph`. Também entrega `build_agent_graph()` — o construtor genérico de grafos LangGraph com topologia `perceive → fast_path → decide → act` — e o `MasterAgent` supervisor com grafo `evaluate_world → dispatch_agents → evaluate_chaos`.

Esta feature é o alicerce sobre o qual todos os agentes concretos (feature 09) são construídos. Sem ela, nenhum agente pode existir: os TypedDicts são o contrato de dados do sistema e o `build_agent_graph()` é o único ponto de construção de grafos do MAS.

---

## Critérios de Aceitação

### Backend — Tipos e Contrato de Interface

- [ ] `backend/src/agents/base.py` exporta `AgentState` como `TypedDict` com os campos exatos de `design.md §7.1`: `world_state`, `entity_id`, `entity_type`, `trigger_event`, `current_tick`, `messages`, `decision_history`, `decision`, `fast_path_taken`, `error`
- [ ] `AgentState.messages` usa `Annotated[list, add_messages]` do `langgraph.graph.message` para acumulação por append
- [ ] `AgentState.entity_type` é `Literal["factory", "warehouse", "store", "truck"]`
- [ ] `WorldStateSlice` exportado por `base.py` contém exatamente: `entity: dict`, `related_entities: list[dict]`, `active_events: list[dict]`, `pending_orders: list[dict]`
- [ ] `DecisionMemory` exportado por `base.py` contém: `tick: int`, `event_type: str`, `action: str`, `summary: str`
- [ ] `AgentDecision` exportado por `base.py` contém: `action: str`, `payload: dict`

### Backend — Construtor de Grafo

- [ ] `build_agent_graph(agent_type: str, tools: list, decision_schema_map: dict) -> CompiledGraph` exportado por `base.py`
- [ ] O grafo compilado tem os cinco nós: `perceive`, `fast_path`, `decide`, `tool_node` (via `ToolNode(tools)`), `act`
- [ ] Entry point é `perceive`
- [ ] Edge `perceive → fast_path` é incondicional
- [ ] Edge condicional `fast_path → END` se `state["fast_path_taken"] == True`, senão `fast_path → decide`
- [ ] Edge condicional `decide → tool_node` se `has_tool_calls(state)`, senão `decide → act`
- [ ] Edge `tool_node → decide` (loop até sem tool calls)
- [ ] Edge `act → END` é incondicional

### Backend — Nó `perceive`

- [ ] `perceive_node` recebe `AgentState` com `entity_id`, `entity_type`, `trigger_event`, `current_tick` já preenchidos
- [ ] Carrega `decision_history` com as últimas N decisões via `AgentDecisionRepository.get_recent_by_entity(entity_id, limit=10)`
- [ ] Monta o system prompt com: identidade do agente, resumo de `WorldStateSlice`, histórico de decisões e `trigger_event`
- [ ] Adiciona o system prompt ao `state["messages"]` como `SystemMessage`

### Backend — Nó `fast_path`

- [ ] `fast_path_node` avalia regras determinísticas antes de chamar o LLM
- [ ] Regra de hold: para qualquer produto `p`, se `stock[p] > HIGH_THRESHOLD` → `fast_path_taken = True`, `decision.action = "hold"`
- [ ] Regra de emergência: se `stock[p] < CRITICAL_THRESHOLD` → `fast_path_taken = True`, `decision.action` reflete pedido de emergência
- [ ] Regra de degradação: se `entity_type == "truck"` e `degradation >= 0.95` → `fast_path_taken = True`, `decision.action = "request_maintenance"`
- [ ] Se nenhuma regra dispara: `fast_path_taken = False`, fluxo segue para `decide`

### Backend — Nó `decide`

- [ ] `decide_node` chama `ChatOpenAI(model=settings.OPENAI_MODEL)` com `llm.bind_tools(tools)` onde `tools` vem do `build_agent_graph()`
- [ ] O LLM retorna uma decisão estruturada no formato JSON esperado pelo guardrail da entidade
- [ ] O `ToolNode` executa as tool calls retornadas pelo `decide` automaticamente (gerenciado pelo LangGraph)

### Backend — Nó `act`

- [ ] `extract_json_from_last_message(messages: list) -> dict` exportado por `base.py`; extrai o JSON da última `AIMessage` com content estruturado
- [ ] `act_node` extrai o JSON da decisão via `extract_json_from_last_message(state["messages"])`
- [ ] Valida via `decision_schema_map[state["entity_type"]](**raw_decision)` (guardrail injetado pelo `build_agent_graph()`)
- [ ] Se guardrail passa: persiste via `AgentDecisionRepository.create()` e publica via `publisher.publish_decision(entity_id, entity_type, decision)`
- [ ] Se guardrail falha (`ValidationError`): retorna `state` com `error = str(e)` e `decision = None` — nada é persistido

### Backend — Helpers

- [ ] `has_tool_calls(state: AgentState) -> bool` exportado por `base.py`; retorna `True` se a última mensagem contém tool calls

### Backend — MasterAgent

- [ ] `backend/src/agents/master_agent.py` exporta `MasterAgent` com grafo compilado `evaluate_world → dispatch_agents → evaluate_chaos → END`
- [ ] `evaluate_world` chama `TriggerEvaluationService.evaluate_all(world_state)` e armazena a lista de `AgentTrigger` no estado interno do grafo
- [ ] `dispatch_agents` cria `asyncio.create_task(agent.run_cycle(trigger))` para cada `AgentTrigger`; aplica `asyncio.Semaphore(MAX_AGENT_WORKERS)` para limitar concorrência de chamadas à OpenAI; fire-and-forget (o tick não aguarda conclusão)
- [ ] `evaluate_chaos` usa `ChatOpenAI` com o contexto do `WorldState`; se o LLM decidir injetar evento, chama `ChaosService.inject_autonomous_event()`; retorno `None` (race condition) é descartado silenciosamente
- [ ] Sub-agentes são instanciados com `entity_id`, `entity_type`, `trigger_event`, `current_tick`; cada sub-agente constrói seu próprio `WorldStateSlice` no nó `perceive` via `WorldStateService`

### Backend — Prompts

- [ ] `backend/src/agents/prompts/factory.md` existe com estrutura de system prompt (stub com seções: identidade, estado atual, objetivo do ciclo, formato de resposta)
- [ ] `backend/src/agents/prompts/warehouse.md` existe com mesma estrutura
- [ ] `backend/src/agents/prompts/store.md` existe com mesma estrutura
- [ ] `backend/src/agents/prompts/truck.md` existe com mesma estrutura

### Testes

- [ ] `perceive_node` com `WorldState` mockado produz `state["messages"][0]` do tipo `SystemMessage` contendo `entity_id` e resumo de `WorldStateSlice`
- [ ] `fast_path_node` retorna `fast_path_taken=True`, `decision.action="hold"` quando `stock[p] > HIGH_THRESHOLD`
- [ ] `fast_path_node` retorna `fast_path_taken=True` com ação de emergência quando `stock[p] < CRITICAL_THRESHOLD`
- [ ] `fast_path_node` retorna `fast_path_taken=True`, `decision.action="request_maintenance"` quando `entity_type="truck"` e `degradation >= 0.95`
- [ ] `fast_path_node` retorna `fast_path_taken=False` para valores na zona de ambiguidade (sem regra ativa)
- [ ] Grafo compilado por `build_agent_graph()` executa `perceive → fast_path → END` com `FakeListChatModel` quando `fast_path_taken=True`
- [ ] Grafo compilado por `build_agent_graph()` executa `perceive → fast_path → decide → act → END` com `FakeListChatModel` quando zona de ambiguidade
- [ ] `act_node` chama `AgentDecisionRepository.create()` e `publisher.publish_decision()` (mocks) quando guardrail stub passa
- [ ] `act_node` retorna `state["error"]` não-nulo e não chama repository quando guardrail falha
- [ ] `has_tool_calls()` retorna `True` para `AIMessage` com `tool_calls` e `False` sem
- [ ] `MasterAgent.dispatch_agents` cria `asyncio.create_task` para cada trigger e não aguarda (verifica via `asyncio.gather` com timeout)

---

## Fora do Escopo

- Implementação dos agentes concretos (`factory_agent.py`, `warehouse_agent.py`, `store_agent.py`, `truck_agent.py`) → feature 09
- Guardrail Pydantic schemas concretos (`FactoryDecision`, `WarehouseDecision`, `StoreDecision`, `TruckDecision`, `AgentDecisionBase`) → feature 10
- Agent tools com `@tool` decorator (`weather`, `route_risk`, `sales_history`) → feature 11
- Lógica interna do `TriggerEvaluationService.evaluate_all()` → feature 07
- Lógica interna do `ChaosService.inject_autonomous_event()` → feature 12
- Conteúdo real dos prompts Markdown (além da estrutura de stub) → feature 09
- Implementação de `WorldStateService` → feature 05
- Implementação de `AgentDecisionRepository` → feature 04
- Implementação de `publisher.publish_decision()` → feature 07
