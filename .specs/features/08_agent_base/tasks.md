# Tasks — Feature 08: Agent Base

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — §3 (estrutura de pastas), §4.2 (MAS / LangGraph / topologia do grafo), §4.4 (simulação / fire-and-forget), §8 (convenções), §9 (TDD obrigatório)
- `.specs/features/08_agent_base/specs.md` — critérios de aceitação desta feature
- `.specs/design.md §7` — schema completo do `AgentState`, `WorldStateSlice`, `DecisionMemory`, topologia do grafo, responsabilidade de cada nó, `MasterAgent`
- `.specs/design.md §9` — estrutura dos guardrails Pydantic (para entender como `act_node` os consome via injeção)
- `.specs/design.md §10.5` — lock de avaliação de contrato para caminhões (contexto para `dispatch_agents` no `MasterAgent`)

Não leia specs de features 09, 10, 11 ou 12 — agentes concretos, guardrails e tools são fora do escopo desta feature.

---

## Plano de Execução

**Fase 1 — Testes (Grupo 1):** Um agente escreve todos os testes. Pausa obrigatória após a conclusão — aguardar aprovação do usuário antes de prosseguir.

**Fase 2 — Implementação (após aprovação dos testes):**
- Grupos 2 e 3 rodam **em paralelo** (sem dependências entre si):
  - Grupo 2: `agents/base.py` — TypedDicts + helpers + nós + `build_agent_graph()`
  - Grupo 3: `agents/prompts/` — stubs dos 4 arquivos Markdown
- Grupo 4 roda **após o Grupo 2** (depende de `AgentState` e `build_agent_graph()` existirem): `agents/master_agent.py`

---

### Grupo 1 — Testes (um agente) — FASE 1

**Tarefa:** Escrever todos os testes unitários da feature. Não implementar nenhum código de produção.

1. Criar `backend/tests/unit/agents/test_base.py`.

2. Importar e usar `FakeListChatModel` de `langchain_core.language_models.fake` para substituir o `ChatOpenAI` nos testes do grafo compilado.

3. Escrever teste para `perceive_node`:
   - Mock de `AgentDecisionRepository.get_recent_by_entity()` retornando lista de `DecisionMemory` stub
   - Mock de `WorldStateSlice` com dados mínimos (entity dict com `id`, `stock`)
   - Verificar que `state["messages"][0]` é `SystemMessage` contendo `entity_id` no texto

4. Escrever testes para `fast_path_node` (todos os ramos):
   - `stock[p] > HIGH_THRESHOLD` → `fast_path_taken=True`, `decision["action"]=="hold"`
   - `stock[p] < CRITICAL_THRESHOLD` → `fast_path_taken=True`, action contém "emergency"
   - `entity_type="truck"`, `degradation=0.95` → `fast_path_taken=True`, `decision["action"]=="request_maintenance"`
   - `degradation=0.94` com estoque na zona de ambiguidade → `fast_path_taken=False`
   - `entity_type="factory"` com estoque na zona de ambiguidade → `fast_path_taken=False`

5. Escrever testes para o grafo compilado via `build_agent_graph()`:
   - Fast path: `AgentState` com `stock > HIGH_THRESHOLD`; verificar que o grafo retorna sem chamar o LLM (spy no `FakeListChatModel`)
   - Full path: `AgentState` na zona de ambiguidade com `FakeListChatModel` retornando JSON de decisão stub; verificar que `act_node` é chamado
   - Tool loop: `FakeListChatModel` configurado para retornar tool call na primeira invocação e decisão na segunda; verificar que `tool_node` é visitado antes do `act`

6. Escrever testes para `act_node`:
   - Guardrail passa: mock `decision_schema_map` aceita o payload → `AgentDecisionRepository.create()` é chamado, `publisher.publish_decision()` é chamado, `state["error"] is None`
   - Guardrail falha: mock `decision_schema_map` lança `ValidationError` → nenhum dos mocks é chamado, `state["error"]` contém a mensagem de erro, `state["decision"] is None`

7. Escrever testes para helpers:
   - `has_tool_calls()` com `AIMessage` contendo `tool_calls` não-vazio → `True`
   - `has_tool_calls()` com `AIMessage` sem `tool_calls` → `False`
   - `extract_json_from_last_message()` com `AIMessage` cujo `content` é string JSON → dict correto
   - `extract_json_from_last_message()` com `AIMessage` cujo `content` é lista com dict JSON → dict correto

8. Escrever testes para `MasterAgent`:
   - `dispatch_agents` com lista de 3 `AgentTrigger` mock → cria 3 tasks via `asyncio.create_task` (verificar via mock/spy)
   - `dispatch_agents` com lista vazia → nenhuma task criada
   - Verificar que `dispatch_agents` não aguarda as tasks (retorna antes da conclusão delas)

**Parar aqui. Não implementar código de produção. Aguardar aprovação do usuário.**

---

### Grupo 2 — `agents/base.py` (um agente) — FASE 2

**Tarefa:** Implementar `AgentState`, helpers, nós e `build_agent_graph()`.

Depende de: aprovação dos testes do Grupo 1.

1. Em `backend/src/agents/base.py`, definir os TypedDicts exatamente conforme `design.md §7.1`:
   - `AgentState` com todos os campos listados em specs.md; `messages` usa `Annotated[list, add_messages]` de `langgraph.graph.message`
   - `WorldStateSlice`: `entity: dict`, `related_entities: list[dict]`, `active_events: list[dict]`, `pending_orders: list[dict]`
   - `DecisionMemory`: `tick: int`, `event_type: str`, `action: str`, `summary: str`
   - `AgentDecision`: `action: str`, `payload: dict`

2. Implementar `has_tool_calls(state: AgentState) -> bool`:
   - Inspeciona a última mensagem de `state["messages"]`
   - Retorna `True` se for `AIMessage` com `tool_calls` não-vazio

3. Implementar `extract_json_from_last_message(messages: list) -> dict`:
   - Pega a última `AIMessage`
   - Se `content` é `str`: usa `json.loads()`
   - Se `content` é `list`: localiza o item com `type == "text"` e faz `json.loads()` do campo `text`
   - Lança `ValueError` se não encontrar JSON válido

4. Implementar `perceive_node(state: AgentState) -> AgentState`:
   - Importa `AgentDecisionRepository` de `src.repositories.agent_decision`
   - Chama `await AgentDecisionRepository().get_recent_by_entity(state["entity_id"], limit=10)` para popular `decision_history`
   - Lê o arquivo de prompt de `src/agents/prompts/{entity_type}.md` e interpola `entity_id`, `trigger_event`, resumo do `WorldStateSlice` e `decision_history`
   - Adiciona `SystemMessage(content=prompt)` a `state["messages"]`
   - Retorna estado atualizado com `decision_history` e `messages`

5. Implementar `fast_path_node(state: AgentState) -> AgentState`:
   - Definir como constantes de módulo: `HIGH_THRESHOLD = 0.85` e `CRITICAL_THRESHOLD = 0.10` (frações do estoque máximo, aplicar sobre `entity.stock` do slice)
   - Regra de hold: se `entity_type in ("factory", "warehouse", "store")` e algum produto tem `stock_ratio > HIGH_THRESHOLD` → `fast_path_taken=True`, `decision={"action": "hold", "payload": {}}`
   - Regra de emergência: se algum produto tem `stock_ratio < CRITICAL_THRESHOLD` → `fast_path_taken=True`, `decision={"action": "emergency_order", "payload": {}}`
   - Regra de degradação: se `entity_type == "truck"` e `entity.degradation >= 0.95` → `fast_path_taken=True`, `decision={"action": "request_maintenance", "payload": {}}`
   - Caso contrário: retorna estado com `fast_path_taken=False`

6. Implementar `decide_node` como closure capturando `llm` e `tools`:
   - Chama `await llm.bind_tools(tools).ainvoke(state["messages"])`
   - Adiciona a resposta a `state["messages"]` (LangGraph gerencia via `add_messages`)
   - Retorna estado atualizado

7. Implementar `act_node` como closure capturando `decision_schema_map`, `db_session` e `publisher_instance`:
   - Chama `extract_json_from_last_message(state["messages"])`
   - Valida via `decision_schema_map[state["entity_type"]](**raw_decision)` — captura `ValidationError`
   - Se válido: chama `await AgentDecisionRepository(db_session).create({...})` e `await publisher_instance.publish_decision(...)`; retorna `{**state, "decision": dict(decision), "error": None}`
   - Se inválido: retorna `{**state, "error": str(e), "decision": None}` — nada é persistido

8. Implementar `build_agent_graph(agent_type: str, tools: list, decision_schema_map: dict, db_session, publisher_instance) -> CompiledGraph`:
   - Instancia `ChatOpenAI(model=settings.OPENAI_MODEL)` internamente
   - Cria as closures para `decide_node` (captura `llm`, `tools`) e `act_node` (captura `decision_schema_map`, `db_session`, `publisher_instance`)
   - Monta `StateGraph(AgentState)` com os nós e edges de `design.md §7.2`
   - Retorna `graph.compile()`

---

### Grupo 3 — `agents/prompts/` (um agente) — FASE 2, paralelo ao Grupo 2

**Tarefa:** Criar os 4 arquivos de system prompt stub.

Depende de: aprovação dos testes do Grupo 1. Não depende do Grupo 2.

1. Criar `backend/src/agents/prompts/factory.md` com esqueleto de system prompt contendo as seções:
   - `# Identidade` — descreve o papel da fábrica; inclui placeholder `{entity_id}`
   - `# Estado Atual` — placeholder `{world_state_summary}`
   - `# Histórico de Decisões` — placeholder `{decision_history}`
   - `# Gatilho` — placeholder `{trigger_event}`
   - `# Formato de Resposta` — instrui retornar JSON: `{"action": "...", "payload": {...}, "reasoning_summary": "..."}`

2. Criar `backend/src/agents/prompts/warehouse.md` com mesma estrutura, identidade ajustada para Armazém.

3. Criar `backend/src/agents/prompts/store.md` com mesma estrutura, identidade ajustada para Loja.

4. Criar `backend/src/agents/prompts/truck.md` com mesma estrutura, identidade ajustada para Caminhão, acrescentando seção `# Perfil` com placeholder `{truck_type}` (proprietario | terceiro).

---

### Grupo 4 — `agents/master_agent.py` (um agente) — FASE 2, após Grupo 2

**Tarefa:** Implementar o `MasterAgent` supervisor.

Depende de: Grupo 2 concluído (`AgentState`, `WorldStateSlice`, `build_agent_graph()` já existem em `agents/base.py`).

1. Em `backend/src/agents/master_agent.py`, definir `MasterAgentState` (TypedDict interno):
   - `world_state: WorldState` — snapshot completo (não slice)
   - `current_tick: int`
   - `triggers: list` — lista de `AgentTrigger`; preenchida por `evaluate_world`
   - `chaos_injected: bool` — preenchida por `evaluate_chaos`

2. Implementar `evaluate_world_node(state: MasterAgentState) -> MasterAgentState`:
   - Chama `await TriggerEvaluationService().evaluate_all(state["world_state"])`
   - Importa `TriggerEvaluationService` de `src.services.trigger_evaluation`
   - Retorna estado com `triggers` preenchido

3. Implementar `dispatch_agents_node` como closure capturando `agent_factory` e `semaphore: asyncio.Semaphore`:
   - Para cada `trigger` em `state["triggers"]`: instancia sub-agente via `agent_factory(trigger.entity_type)` e cria `asyncio.create_task(semaphore_wrap(semaphore, agent.run_cycle(trigger)))`
   - `semaphore_wrap` é coroutine local: `async def semaphore_wrap(sem, coro): async with sem: await coro`
   - Fire-and-forget: não aguarda as tasks; retorna estado inalterado imediatamente

4. Implementar `evaluate_chaos_node` como closure capturando `llm`:
   - Monta prompt com resumo do `WorldState` (entidades em stress, ticks desde último evento autônomo)
   - Chama `await llm.ainvoke([HumanMessage(content=prompt)])`
   - Se resposta indicar injeção de evento: chama `await ChaosService().inject_autonomous_event(data)` (importa de `src.services.chaos`)
   - Retorno `None` de `inject_autonomous_event` (race condition) → descarta silenciosamente, `chaos_injected=False`
   - Retorna estado com `chaos_injected` atualizado

5. Montar e compilar o grafo `MasterAgent` com topologia `evaluate_world → dispatch_agents → evaluate_chaos → END`.

6. Exportar `run_master_cycle(world_state: WorldState, current_tick: int, db_session, publisher_instance) -> None`:
   - Instancia estado inicial `MasterAgentState`
   - Invoca `await master_agent.ainvoke(initial_state)`

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
`pytest backend/tests/unit/agents/test_base.py` passa com zero falhas.
Nenhum erro de import em `backend/src/agents/base.py` e `backend/src/agents/master_agent.py`.
Atualizar `state.md`: setar o status da feature `08` para `done`.
