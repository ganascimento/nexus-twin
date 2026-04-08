# Feature 11 — Agent Tools

## Objetivo

Implementar as ferramentas (`@tool`) que os agentes LLM utilizam durante o nó `decide` do StateGraph para consultar informações externas ao `WorldStateSlice` antes de tomar uma decisão. Atualmente os agentes são construídos com `tools=[]` — esta feature entrega as 5 ferramentas reais e as conecta aos agentes correspondentes, habilitando o loop `decide → tool_node → decide` descrito em `CLAUDE.md §4.2`.

As ferramentas são stateless — recebem parâmetros tipados e retornam Pydantic models. Não alteram o banco de dados; apenas lêem dados para alimentar o contexto do LLM.

---

## Critérios de Aceitação

### Backend — `tools/weather.py`

- [ ] Função `weather` decorada com `@tool` do `langchain_core.tools`
- [ ] Recebe parâmetros tipados: `lat: float`, `lng: float`
- [ ] Retorna um Pydantic model com campos: `condition` (str), `severity` (Literal["none", "low", "medium", "high"]), `description` (str)
- [ ] Implementação simulada (sem API externa real) — retorna dados determinísticos ou mock baseados em coordenadas/seed para permitir testes reproduzíveis
- [ ] O agente Truck usa esta tool (ver tabela em `design.md §7.3`)

### Backend — `tools/route_risk.py`

- [ ] Função `route_risk` decorada com `@tool`
- [ ] Recebe parâmetros tipados: `origin_lat: float`, `origin_lng: float`, `dest_lat: float`, `dest_lng: float`
- [ ] Retorna um Pydantic model com campos: `risk_level` (Literal["low", "medium", "high"]), `factors` (list[str]), `estimated_delay_hours` (float)
- [ ] Implementação simulada — calcula risco com base na distância e em fatores determinísticos (sem API externa)
- [ ] O agente Truck usa esta tool (ver tabela em `design.md §7.3`)

### Backend — `tools/sales_history.py`

- [ ] Função `sales_history` decorada com `@tool`
- [ ] Recebe parâmetros tipados: `entity_id: str`, `material_id: str`, `last_n_ticks: int`
- [ ] Retorna um Pydantic model com campos: `entity_id` (str), `material_id` (str), `total_sold` (float), `average_per_tick` (float), `trend` (Literal["increasing", "stable", "decreasing"])
- [ ] Implementação simulada — retorna dados determinísticos baseados nos parâmetros de entrada
- [ ] Os agentes Factory, Warehouse e Store usam esta tool (ver tabela em `design.md §7.3`)

### Backend — `tools/stock_levels.py` (novo arquivo)

- [ ] Função `warehouse_stock_levels` decorada com `@tool`
  - Recebe: `warehouse_id: str`
  - Retorna Pydantic model com: `warehouse_id` (str), `stocks` (list[dict] com `material_id`, `quantity`, `capacity_remaining`)
  - Implementação simulada — retorna dados determinísticos
  - Usada pelos agentes Factory e Store

- [ ] Função `factory_stock_levels` decorada com `@tool`
  - Recebe: `factory_id: str`
  - Retorna Pydantic model com: `factory_id` (str), `products` (list[dict] com `material_id`, `stock`, `stock_max`, `production_rate_current`)
  - Implementação simulada — retorna dados determinísticos
  - Usada pelo agente Warehouse

### Backend — `tools/__init__.py`

- [ ] Re-exporta todas as 5 ferramentas: `weather`, `route_risk`, `sales_history`, `warehouse_stock_levels`, `factory_stock_levels`
- [ ] Exporta constantes de agrupamento por agente:
  - `FACTORY_TOOLS = [sales_history, warehouse_stock_levels]`
  - `WAREHOUSE_TOOLS = [sales_history, factory_stock_levels]`
  - `STORE_TOOLS = [sales_history, warehouse_stock_levels]`
  - `TRUCK_TOOLS = [weather, route_risk]`

### Backend — Integração com Agentes

- [ ] `FactoryAgent.run_cycle()` passa `FACTORY_TOOLS` em vez de `tools=[]` ao chamar `build_agent_graph()`
- [ ] `WarehouseAgent.run_cycle()` passa `WAREHOUSE_TOOLS` em vez de `tools=[]`
- [ ] `StoreAgent.run_cycle()` passa `STORE_TOOLS` em vez de `tools=[]`
- [ ] `TruckAgent.run_cycle()` passa `TRUCK_TOOLS` em vez de `tools=[]`

### Backend — Testes Unitários

- [ ] Cada tool tem testes em `backend/tests/unit/tools/` verificando:
  - Retorno com parâmetros válidos (tipo correto, campos presentes)
  - Que a função é decorada com `@tool` (verificável via atributos do decorator)
- [ ] Testes de integração das listas de tools por agente: cada lista contém exatamente as tools esperadas conforme `design.md §7.3`

---

## Fora do Escopo

- Integração com APIs externas reais (clima, roteamento) — todas as tools são simuladas nesta feature; integração real com Valhalla é da feature de rotas
- Lógica do `ToolNode` no grafo — já implementada em `agents/base.py` (feature 08)
- Alterações no `build_agent_graph()` — a função já aceita `tools: list` e constrói o `ToolNode`
- Testes end-to-end com LLM chamando as tools — o loop `decide → tool_node → decide` já funciona via `ToolNode` do LangGraph; aqui testamos apenas as tools isoladamente
- Prompts dos agentes — já escritos na feature 09
