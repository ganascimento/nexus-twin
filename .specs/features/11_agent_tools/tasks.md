# Tasks — Feature 11: Agent Tools

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:
- `CLAUDE.md` — estrutura de pastas (§3), tools dos agentes (§4.3), convenções (§8)
- `.specs/features/11_agent_tools/specs.md` — critérios de aceitação
- `.specs/design.md` seção 7.3 (tabela de tools por agente)
- `backend/src/agents/base.py` — `build_agent_graph()`, `ToolNode`, `has_tool_calls()`
- `backend/src/agents/factory_agent.py` — referência de como `tools=[]` é passado hoje
- `backend/src/agents/warehouse_agent.py`
- `backend/src/agents/store_agent.py`
- `backend/src/agents/truck_agent.py`
- `backend/src/tools/__init__.py` — stub atual

---

## Plano de Execução

**Fase 1 (TDD):** Grupo 1 escreve todos os testes. Pausa obrigatória antes de implementar.

**Fase 2 (Implementação):** Grupos 2 e 3 rodam sequencialmente — Grupo 2 implementa as tools, Grupo 3 integra as tools nos agentes (depende dos exports do Grupo 2).

---

### Grupo 1 — Testes (TDD Fase 1)

**Tarefa:** Escrever todos os testes unitários para as 5 tools e para a integração com os agentes.

1. Criar `backend/tests/unit/tools/__init__.py`

2. Criar `backend/tests/unit/tools/test_weather.py`:
   - Testar que `weather` é callable e possui atributo de `@tool` (ex: `hasattr(weather, 'name')`)
   - Testar chamada com coordenadas válidas (`lat=-23.55, lng=-46.63`) retorna objeto com campos `condition`, `severity`, `description`
   - Testar que `severity` é um dos valores válidos: `"none"`, `"low"`, `"medium"`, `"high"`

3. Criar `backend/tests/unit/tools/test_route_risk.py`:
   - Testar que `route_risk` é callable e possui atributo de `@tool`
   - Testar chamada com 4 coordenadas válidas retorna objeto com `risk_level`, `factors`, `estimated_delay_hours`
   - Testar que `risk_level` é um dos valores: `"low"`, `"medium"`, `"high"`
   - Testar que `factors` é uma lista de strings
   - Testar que `estimated_delay_hours` é `>= 0`

4. Criar `backend/tests/unit/tools/test_sales_history.py`:
   - Testar que `sales_history` é callable e possui atributo de `@tool`
   - Testar chamada com `entity_id`, `material_id`, `last_n_ticks` retorna objeto com `entity_id`, `material_id`, `total_sold`, `average_per_tick`, `trend`
   - Testar que `trend` é um dos valores: `"increasing"`, `"stable"`, `"decreasing"`
   - Testar que `total_sold >= 0` e `average_per_tick >= 0`

5. Criar `backend/tests/unit/tools/test_stock_levels.py`:
   - Testar que `warehouse_stock_levels` é callable e possui atributo de `@tool`
   - Testar chamada com `warehouse_id` retorna objeto com `warehouse_id` e `stocks` (lista)
   - Testar que cada item em `stocks` tem `material_id`, `quantity`, `capacity_remaining`
   - Testar que `factory_stock_levels` é callable e possui atributo de `@tool`
   - Testar chamada com `factory_id` retorna objeto com `factory_id` e `products` (lista)
   - Testar que cada item em `products` tem `material_id`, `stock`, `stock_max`, `production_rate_current`

6. Criar `backend/tests/unit/tools/test_tool_groups.py`:
   - Importar `FACTORY_TOOLS`, `WAREHOUSE_TOOLS`, `STORE_TOOLS`, `TRUCK_TOOLS` de `src.tools`
   - Testar que `FACTORY_TOOLS` contém exatamente `[sales_history, warehouse_stock_levels]`
   - Testar que `WAREHOUSE_TOOLS` contém exatamente `[sales_history, factory_stock_levels]`
   - Testar que `STORE_TOOLS` contém exatamente `[sales_history, warehouse_stock_levels]`
   - Testar que `TRUCK_TOOLS` contém exatamente `[weather, route_risk]`

**Parar aqui. Não implementar código de produção. Aguardar aprovação do usuário.**

---

### Grupo 2 — Implementação das Tools (um agente)

**Tarefa:** Implementar as 5 ferramentas com decorator `@tool` e modelos de retorno Pydantic.

1. Substituir `backend/src/tools/weather.py`:
   - Criar `WeatherResult(BaseModel)` com `condition: str`, `severity: Literal["none", "low", "medium", "high"]`, `description: str`
   - Implementar `@tool` function `weather(lat: float, lng: float) -> WeatherResult`
   - Lógica simulada: usar hash das coordenadas para gerar resultado determinístico (ex: `abs(hash((round(lat,2), round(lng,2)))) % 4` mapeia para um severity)

2. Substituir `backend/src/tools/route_risk.py`:
   - Criar `RouteRiskResult(BaseModel)` com `risk_level: Literal["low", "medium", "high"]`, `factors: list[str]`, `estimated_delay_hours: float`
   - Implementar `@tool` function `route_risk(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> RouteRiskResult`
   - Lógica simulada: calcular distância euclidiana entre pontos; distância maior = risco maior. Fatores gerados deterministicamente com base na distância.

3. Substituir `backend/src/tools/sales_history.py`:
   - Criar `SalesHistoryResult(BaseModel)` com `entity_id: str`, `material_id: str`, `total_sold: float`, `average_per_tick: float`, `trend: Literal["increasing", "stable", "decreasing"]`
   - Implementar `@tool` function `sales_history(entity_id: str, material_id: str, last_n_ticks: int) -> SalesHistoryResult`
   - Lógica simulada: retornar valores determinísticos baseados em hash dos parâmetros

4. Criar `backend/src/tools/stock_levels.py`:
   - Criar `WarehouseStockItem(BaseModel)` com `material_id: str`, `quantity: float`, `capacity_remaining: float`
   - Criar `WarehouseStockResult(BaseModel)` com `warehouse_id: str`, `stocks: list[WarehouseStockItem]`
   - Implementar `@tool` function `warehouse_stock_levels(warehouse_id: str) -> WarehouseStockResult`
   - Criar `FactoryProductItem(BaseModel)` com `material_id: str`, `stock: float`, `stock_max: float`, `production_rate_current: float`
   - Criar `FactoryStockResult(BaseModel)` com `factory_id: str`, `products: list[FactoryProductItem]`
   - Implementar `@tool` function `factory_stock_levels(factory_id: str) -> FactoryStockResult`
   - Lógica simulada para ambas: retornar dados determinísticos baseados em hash do ID

5. Atualizar `backend/src/tools/__init__.py`:
   - Importar e re-exportar: `weather`, `route_risk`, `sales_history`, `warehouse_stock_levels`, `factory_stock_levels`
   - Definir constantes:
     ```python
     FACTORY_TOOLS = [sales_history, warehouse_stock_levels]
     WAREHOUSE_TOOLS = [sales_history, factory_stock_levels]
     STORE_TOOLS = [sales_history, warehouse_stock_levels]
     TRUCK_TOOLS = [weather, route_risk]
     ```

---

### Grupo 3 — Integração com Agentes (um agente, após Grupo 2)

**Tarefa:** Substituir `tools=[]` nas chamadas a `build_agent_graph()` de cada agente concreto pelas listas de tools reais.

1. Editar `backend/src/agents/factory_agent.py`:
   - Importar `FACTORY_TOOLS` de `src.tools`
   - Alterar `tools=[]` para `tools=FACTORY_TOOLS` na chamada a `build_agent_graph()`

2. Editar `backend/src/agents/warehouse_agent.py`:
   - Importar `WAREHOUSE_TOOLS` de `src.tools`
   - Alterar `tools=[]` para `tools=WAREHOUSE_TOOLS`

3. Editar `backend/src/agents/store_agent.py`:
   - Importar `STORE_TOOLS` de `src.tools`
   - Alterar `tools=[]` para `tools=STORE_TOOLS`

4. Editar `backend/src/agents/truck_agent.py`:
   - Importar `TRUCK_TOOLS` de `src.tools`
   - Alterar `tools=[]` para `tools=TRUCK_TOOLS`

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes passam com `pytest backend/tests/unit/tools/`.
Atualizar `state.md`: setar o status da feature `11` para `done`.
