# Tasks — Feature 13: API REST

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — estrutura de pastas (§3), convenções (§8), TDD (§9)
- `.specs/features/13_api_rest/specs.md` — critérios de aceitação
- `.specs/design.md` §2 — todos os endpoints HTTP com paths e métodos exatos
- `.specs/design.md` §6 — assinaturas dos services que a API consome
- `.specs/design.md` §10.4 — regras de deleção de entidades com pedidos pendentes
- `backend/src/main.py` — entry point do FastAPI (onde registrar os routers)
- `backend/src/services/*.py` — assinaturas dos services implementados
- `backend/src/database/session.py` — dependency `get_db`

Referência para DTOs existentes no projeto system-atlas:
- `/home/gan/projects/system-atlas/system-atlas-core/system_atlas_core/dtos/` — padrão de Pydantic schemas de request/response (usar como referência de estilo, não copiar)

---

## Plano de Execução

Feature com TDD obrigatório. Execução em 2 fases com paralelismo interno:

1. **Grupo 1** (TDD — Fase 1) — Escrever todos os testes. Subagentes em paralelo por domínio. Parar e aguardar aprovação.
2. **Grupo 2** (Implementação) — Implementar os endpoints. Subagentes em paralelo por domínio. Só após aprovação dos testes.

---

### Grupo 1 — Testes Unitários (TDD — Fase 1)

Os subagentes abaixo podem rodar **em paralelo** (cada um cobre um arquivo de rotas independente).

#### Subagente 1A — Testes de Simulação e World

**Tarefa:** Criar testes para `routes/simulation.py` e `routes/world.py`.

1. Criar `backend/tests/unit/api/__init__.py` e `backend/tests/unit/api/routes/__init__.py` (se não existirem)
2. Criar `backend/tests/unit/api/routes/test_simulation.py`:
   - Fixture: `httpx.AsyncClient` com `ASGITransport(app=app)`, `SimulationService` mockado via `app.dependency_overrides`
   - `test_start_simulation` — `POST /api/v1/simulation/start` retorna `200`
   - `test_stop_simulation` — `POST /api/v1/simulation/stop` retorna `200`
   - `test_advance_tick_when_stopped` — `POST /api/v1/simulation/tick` retorna `200` com WorldState
   - `test_advance_tick_when_running_returns_409` — simulação rodando, retorna `409`
   - `test_get_status` — `GET /api/v1/simulation/status` retorna status completo
   - `test_set_speed_valid` — `PATCH /api/v1/simulation/speed` com valor ≥ 10 retorna `200`
   - `test_set_speed_below_minimum_returns_400` — valor < 10 retorna `400`
3. Criar `backend/tests/unit/api/routes/test_world.py`:
   - `test_get_snapshot` — `GET /api/v1/world/snapshot` retorna payload completo
   - `test_get_tick` — `GET /api/v1/world/tick` retorna tick e timestamp

#### Subagente 1B — Testes de Materiais

**Tarefa:** Criar testes para `routes/materials.py`.

1. Criar `backend/tests/unit/api/routes/test_materials.py`:
   - Fixture: `httpx.AsyncClient`, `MaterialService` mockado
   - `test_list_materials` — `GET /api/v1/materials` retorna lista
   - `test_list_materials_active_only` — `GET /api/v1/materials?active_only=true` filtra ativos
   - `test_create_material` — `POST /api/v1/materials` retorna `201`
   - `test_update_material` — `PATCH /api/v1/materials/{id}` retorna `200`
   - `test_update_material_not_found` — `404` para id inexistente
   - `test_deactivate_material` — `PATCH /api/v1/materials/{id}/deactivate` retorna `200`
   - `test_deactivate_material_with_linked_entities_returns_409` — `409` quando há vínculos

#### Subagente 1C — Testes de Fábricas e Armazéns

**Tarefa:** Criar testes para `routes/factories.py` e `routes/warehouses.py`.

1. Criar `backend/tests/unit/api/routes/test_factories.py`:
   - Fixture: `httpx.AsyncClient`, `FactoryService` mockado
   - `test_list_factories` — `GET /api/v1/entities/factories` retorna lista
   - `test_get_factory` — `GET /api/v1/entities/factories/{id}` retorna detalhe
   - `test_get_factory_not_found` — `404`
   - `test_create_factory` — `POST /api/v1/entities/factories` retorna `201`
   - `test_update_factory` — `PATCH /api/v1/entities/factories/{id}` retorna `200`
   - `test_update_factory_not_found` — `404`
   - `test_delete_factory` — `DELETE /api/v1/entities/factories/{id}` retorna `200`
   - `test_delete_factory_not_found` — `404`
   - `test_adjust_factory_stock` — `PATCH /api/v1/entities/factories/{id}/stock` retorna `200`
   - `test_adjust_factory_stock_not_found` — `404`
2. Criar `backend/tests/unit/api/routes/test_warehouses.py`:
   - Mesma estrutura de `test_factories.py` adaptada para armazéns
   - Inclui testes para `GET`, `POST`, `PATCH`, `DELETE` e `PATCH .../stock`
   - Cenários de `404` para cada operação com id inexistente

#### Subagente 1D — Testes de Lojas e Caminhões

**Tarefa:** Criar testes para `routes/stores.py` e `routes/trucks.py`.

1. Criar `backend/tests/unit/api/routes/test_stores.py`:
   - Mesma estrutura de `test_factories.py` adaptada para lojas
   - Inclui testes para `GET`, `POST`, `PATCH`, `DELETE` e `PATCH .../stock`
   - Cenários de `404` para cada operação
2. Criar `backend/tests/unit/api/routes/test_trucks.py`:
   - Fixture: `httpx.AsyncClient`, `TruckService` mockado
   - `test_list_trucks` — `GET /api/v1/entities/trucks` retorna lista
   - `test_get_truck` — `GET /api/v1/entities/trucks/{id}` retorna detalhe
   - `test_get_truck_not_found` — `404`
   - `test_create_truck` — `POST /api/v1/entities/trucks` retorna `201`
   - `test_delete_truck` — `DELETE /api/v1/entities/trucks/{id}` retorna `200`
   - `test_delete_truck_not_found` — `404`

#### Subagente 1E — Testes de Caos e Decisões

**Tarefa:** Criar testes para `routes/chaos.py` e `routes/decisions.py`.

1. Criar `backend/tests/unit/api/routes/test_chaos.py`:
   - Fixture: `httpx.AsyncClient`, `ChaosService` mockado
   - `test_list_active_events` — `GET /api/v1/chaos/events` retorna lista
   - `test_inject_event` — `POST /api/v1/chaos/events` retorna `201`
   - `test_resolve_event` — `POST /api/v1/chaos/events/{id}/resolve` retorna `200`
   - `test_resolve_event_not_found` — `404`
   - `test_resolve_event_already_resolved` — `409`
2. Criar `backend/tests/unit/api/routes/test_decisions.py`:
   - Fixture: `httpx.AsyncClient`, `AgentDecisionRepository` ou service mockado
   - `test_list_decisions` — `GET /api/v1/decisions` retorna lista
   - `test_list_decisions_with_filters` — `GET /api/v1/decisions?entity_id=X&limit=10`
   - `test_get_decisions_for_entity` — `GET /api/v1/decisions/{entity_id}` retorna histórico
   - `test_get_decisions_for_nonexistent_entity` — `404`

**⚠ Parar aqui. Não implementar código de produção. Aguardar aprovação do usuário.**

---

### Grupo 2 — Implementação dos Endpoints

Os subagentes abaixo podem rodar **em paralelo** (cada um implementa rotas independentes).

#### Subagente 2A — Simulação e World

**Tarefa:** Implementar `routes/simulation.py` e `routes/world.py`.

1. Implementar `backend/src/api/routes/simulation.py`:
   - `APIRouter(prefix="/simulation", tags=["simulation"])`
   - Dependency: `SimulationService` via `Depends`
   - Endpoints conforme `design.md §2 — Simulação`
   - `advance_tick`: verificar se simulação está rodando antes de avançar; retornar `409` se sim
   - `set_speed`: validar mínimo 10 segundos; retornar `400` se inválido

2. Implementar `backend/src/api/routes/world.py`:
   - `APIRouter(prefix="/world", tags=["world"])`
   - Dependency: `WorldStateService` via `Depends`
   - `get_snapshot`: retorna `WorldStatePayload`
   - `get_tick`: retorna tick atual e timestamp

#### Subagente 2B — Materiais

**Tarefa:** Implementar `routes/materials.py`.

1. Implementar `backend/src/api/routes/materials.py`:
   - `APIRouter(prefix="/materials", tags=["materials"])`
   - Dependency: `MaterialService` via `Depends`
   - Schemas Pydantic: `MaterialCreate`, `MaterialUpdate`, `MaterialResponse`
   - Endpoints conforme `design.md §2 — Materiais`
   - `deactivate`: capturar exceção do service e retornar `409` se há entidades vinculadas

#### Subagente 2C — Fábricas e Armazéns

**Tarefa:** Implementar `routes/factories.py` e `routes/warehouses.py`.

1. Implementar `backend/src/api/routes/factories.py`:
   - `APIRouter(prefix="/entities/factories", tags=["factories"])`
   - Dependency: `FactoryService` via `Depends`
   - Schemas Pydantic: `FactoryCreate`, `FactoryUpdate`, `StockAdjust`, `FactoryResponse`, `FactoryDetailResponse`
   - Endpoints conforme `design.md §2 — Fábricas`
   - `delete`: delega cascade de pedidos ao `FactoryService.delete_factory()`

2. Implementar `backend/src/api/routes/warehouses.py`:
   - Mesma estrutura de `factories.py` adaptada para armazéns
   - Schemas: `WarehouseCreate`, `WarehouseUpdate`, `StockAdjust`, `WarehouseResponse`

#### Subagente 2D — Lojas e Caminhões

**Tarefa:** Implementar `routes/stores.py` e `routes/trucks.py`.

1. Implementar `backend/src/api/routes/stores.py`:
   - Mesma estrutura de `factories.py` adaptada para lojas
   - Schemas: `StoreCreate`, `StoreUpdate`, `StockAdjust`, `StoreResponse`

2. Implementar `backend/src/api/routes/trucks.py`:
   - `APIRouter(prefix="/entities/trucks", tags=["trucks"])`
   - Dependency: `TruckService` via `Depends`
   - Schemas: `TruckCreate`, `TruckResponse`, `TruckDetailResponse`
   - Sem `PATCH` (caminhões não são editáveis pelo usuário)

#### Subagente 2E — Caos, Decisões e Registro de Routers

**Tarefa:** Implementar `routes/chaos.py`, `routes/decisions.py` e registrar todos os routers no app.

1. Implementar `backend/src/api/routes/chaos.py`:
   - `APIRouter(prefix="/chaos", tags=["chaos"])`
   - Dependency: `ChaosService` via `Depends`
   - Schemas: `ChaosEventCreate`, `ChaosEventResponse`
   - `inject_event`: apenas eventos manuais (`source="user"`)
   - `resolve_event`: capturar exceções do service para `404` e `409`

2. Implementar `backend/src/api/routes/decisions.py`:
   - `APIRouter(prefix="/decisions", tags=["decisions"])`
   - Dependency: `AgentDecisionRepository` ou service dedicado via `Depends`
   - Query params: `entity_id` (opcional), `limit` (opcional, default 50)

3. Registrar todos os routers em `backend/src/main.py`:
   - Importar todos os routers de `api/routes/`
   - `app.include_router(router, prefix="/api/v1")` para cada um

4. Criar dependency factories (`get_<service>`) se ainda não existirem:
   - Em `backend/src/api/dependencies.py` ou inline nos routers
   - Padrão: `async def get_factory_service(db: AsyncSession = Depends(get_db)) -> FactoryService`

5. Rodar `pytest backend/tests/unit/api/ -v` — todos os testes devem passar

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes passam com `pytest`.
Atualizar `state.md`: setar o status da feature `13` para `done`.
