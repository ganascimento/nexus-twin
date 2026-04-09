# Tasks — Feature 15: Celery Workers

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — workers (§4.5 Celery), convencoes (§8), dependencias (§5), variaveis de ambiente (§6)
- `.specs/features/15_celery_workers/specs.md` — criterios de aceitacao
- `.specs/design.md §4` — definicao das tasks Celery (nomes, triggers, descricoes)
- `backend/src/database/session.py` — session factory async (referencia para criar a versao sincrona)
- `backend/src/database/models/` — ORM models usados nas queries das tasks
- `backend/src/main.py` — entry point onde as novas rotas serao registradas

---

## Plano de Execucao

Grupo 1 e a fase de testes (TDD Phase 1) — parar apos criar os testes e aguardar aprovacao.
Grupos 2 e 3 podem rodar em paralelo (infraestrutura Celery + endpoints REST sao independentes).
Grupo 4 e sequencial — registra as rotas no app apos os grupos anteriores.

---

### Grupo 1 — Testes (TDD Phase 1)

**Tarefa:** Escrever testes unitarios para as tasks Celery e os endpoints REST.

1. Criar `backend/tests/unit/workers/__init__.py` e `backend/tests/unit/workers/tasks/__init__.py`

2. Criar `backend/tests/unit/workers/tasks/test_reports.py`:
   - Testar `generate_efficiency_report`:
     - Com dados mockados: pedidos (2 delivered, 1 late com `age_ticks > eta_ticks`), lojas com ruptura de estoque (`stock = 0` em um produto), caminhoes (1 `in_transit`, 1 `idle`)
     - Verificar que resultado contem `orders_delivered`, `orders_late`, `stock_ruptures` e `truck_utilization` com valores corretos
   - Testar `generate_decision_summary`:
     - Com decisoes mockadas de tipos variados (`factory/start_production`, `warehouse/request_resupply`, `truck/accept_contract`)
     - Verificar agrupamento correto por `agent_type` e `action` com contagens
     - Verificar que intervalo de ticks padrao (24) e respeitado quando nao especificado

3. Criar `backend/tests/unit/workers/tasks/test_exports.py`:
   - Testar `export_decision_history`: verificar que retorna lista de dicts com campos esperados (`tick`, `agent_type`, `entity_id`, `action`, `reasoning_summary`); testar filtro por `entity_id` e `limit`
   - Testar `export_event_history`: verificar que retorna lista de eventos com campos `event_type`, `status`, `tick_start`, `tick_end`, `entity_type`, `entity_id`
   - Testar `export_world_snapshot`: verificar que retorna dict com chaves `factories`, `warehouses`, `stores`, `trucks`

4. Criar `backend/tests/unit/api/routes/test_reports.py`:
   - Testar `POST /api/v1/reports/efficiency` retorna 202 com `{ "task_id": "..." }` (mockar `generate_efficiency_report.delay()`)
   - Testar `POST /api/v1/reports/decisions` retorna 202 com `task_id` (mockar `generate_decision_summary.delay()`)
   - Testar `POST /api/v1/reports/decisions` com parametro `ticks` customizado

5. Criar `backend/tests/unit/api/routes/test_exports.py`:
   - Testar `POST /api/v1/exports/decisions` retorna 202 com `task_id`
   - Testar `POST /api/v1/exports/events` retorna 202 com `task_id`
   - Testar `POST /api/v1/exports/world-snapshot` retorna 202 com `task_id`
   - Testar `POST /api/v1/exports/decisions` com filtros opcionais `entity_id` e `limit`

6. Criar `backend/tests/unit/api/routes/test_tasks.py`:
   - Testar `GET /api/v1/tasks/{task_id}/status` retorna estado `PENDING` para task inexistente/pendente
   - Testar retorno com `SUCCESS` inclui o `result`
   - Testar retorno com `FAILURE` inclui `error`

Mockar a sessao de banco (SQLAlchemy sincrona) nos testes das tasks. Mockar `.delay()` retornando `AsyncResult` fake nos testes de rota.

**Parar aqui. Nao implementar codigo de producao. Aguardar aprovacao do usuario.**

---

### Grupo 2 — Infraestrutura Celery + Tasks (um agente)

**Tarefa:** Implementar a instancia Celery, sessao sincrona e todas as tasks.

1. Implementar `backend/src/workers/celery_app.py`:
   - `import os` e `from celery import Celery`
   - Ler `REDIS_URL` do ambiente (padrao `redis://localhost:6379`)
   - `celery_app = Celery("nexus_twin", broker=REDIS_URL, backend=REDIS_URL)`
   - Configurar: `task_serializer = "json"`, `result_serializer = "json"`, `accept_content = ["json"]`
   - `celery_app.autodiscover_tasks(["src.workers.tasks"])`
   - Criar `get_sync_session()`:
     - Ler `DATABASE_URL` do ambiente
     - Converter `postgresql+asyncpg://` para `postgresql://` (replace do scheme)
     - `engine = create_engine(sync_url)`
     - `SessionLocal = sessionmaker(bind=engine)`
     - Retornar `SessionLocal()` como context manager

2. Implementar `backend/src/workers/tasks/reports.py`:

   a. `@shared_task(name="generate_efficiency_report") def generate_efficiency_report()`:
      - Abrir sessao sincrona via `get_sync_session()`
      - Query `pending_orders`: contar com `status = 'delivered'` → `orders_delivered`; contar com `status = 'delivered'` e `age_ticks > eta_ticks` → `orders_late`
      - Query lojas (`store_stocks`) e armazens (`warehouse_stocks`): listar entidades com `stock = 0` em algum produto → `stock_ruptures` (lista de `{entity_type, entity_id, material_id}`)
      - Query caminhoes: para cada caminhao, contar decisoes com acao que indica transito vs. idle no historico → `truck_utilization` (simplificado: usar status atual como proxy)
      - Fechar sessao; retornar dict

   b. `@shared_task(name="generate_decision_summary") def generate_decision_summary(tick_start=None, tick_end=None)`:
      - Se `tick_start`/`tick_end` nao fornecidos: calcular ultimos 24 ticks com base no tick maximo registrado em `agent_decisions`
      - Query `agent_decisions` no intervalo
      - Agrupar por `agent_type` e `action` com `func.count()`
      - Retornar dict `{ agent_type: { action: count } }`

3. Implementar `backend/src/workers/tasks/exports.py`:

   a. `@shared_task(name="export_decision_history") def export_decision_history(entity_id=None, limit=None)`:
      - Query `agent_decisions` com filtros opcionais
      - Serializar cada registro para dict: `tick`, `agent_type`, `entity_id`, `action`, `reasoning_summary`, `created_at` (ISO format)
      - Retornar lista de dicts

   b. `@shared_task(name="export_event_history") def export_event_history()`:
      - Query `events` (todos, nao apenas ativos)
      - Serializar: `id`, `event_type`, `source`, `entity_type`, `entity_id`, `status`, `tick_start`, `tick_end`, `description`, `created_at`
      - Retornar lista de dicts

   c. `@shared_task(name="export_world_snapshot") def export_world_snapshot()`:
      - Query factories com `factory_products`, warehouses com `warehouse_stocks`, stores com `store_stocks`, trucks
      - Montar dict com chaves `factories`, `warehouses`, `stores`, `trucks`
      - Cada entidade serializada com seus campos relevantes
      - Retornar dict

---

### Grupo 3 — Endpoints REST (um agente, paralelo ao Grupo 2)

**Tarefa:** Criar os schemas Pydantic e as rotas REST para acionar tasks e consultar status.

1. Criar `backend/src/api/models/tasks.py`:
   - `TaskResponse(BaseModel)`: `task_id: str`
   - `TaskStatusResponse(BaseModel)`: `task_id: str`, `status: str`, `result: dict | list | None = None`, `error: str | None = None`
   - `DecisionSummaryRequest(BaseModel)`: `ticks: int = 24`
   - `DecisionExportRequest(BaseModel)`: `entity_id: str | None = None`, `limit: int | None = None`

2. Criar `backend/src/api/routes/reports.py`:
   - Router com prefix `/reports`
   - `POST /efficiency`: importar `generate_efficiency_report`, chamar `.delay()`, retornar `TaskResponse(task_id=result.id)` com status 202
   - `POST /decisions`: receber `DecisionSummaryRequest` no body, calcular `tick_start`/`tick_end` a partir de `ticks`, chamar `generate_decision_summary.delay(tick_start, tick_end)`, retornar 202

3. Criar `backend/src/api/routes/exports.py`:
   - Router com prefix `/exports`
   - `POST /decisions`: receber `DecisionExportRequest`, chamar `export_decision_history.delay(entity_id, limit)`, retornar 202
   - `POST /events`: chamar `export_event_history.delay()`, retornar 202
   - `POST /world-snapshot`: chamar `export_world_snapshot.delay()`, retornar 202

4. Criar `backend/src/api/routes/tasks.py`:
   - Router com prefix `/tasks`
   - `GET /{task_id}/status`: criar `AsyncResult(task_id, app=celery_app)`, retornar `TaskStatusResponse` com `status`, `result` (se SUCCESS) e `error` (se FAILURE com `str(result.result)`)

---

### Grupo 4 — Registro de Rotas (sequencial, apos Grupos 2 e 3)

**Tarefa:** Registrar as novas rotas no app FastAPI.

1. Atualizar `backend/src/main.py`:
   - Importar `reports_router` de `src.api.routes.reports`
   - Importar `exports_router` de `src.api.routes.exports`
   - Importar `tasks_router` de `src.api.routes.tasks`
   - `app.include_router(reports_router, prefix=API_V1_PREFIX)`
   - `app.include_router(exports_router, prefix=API_V1_PREFIX)`
   - `app.include_router(tasks_router, prefix=API_V1_PREFIX)`

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos.
Todos os testes passam com `pytest`.
Atualizar `state.md`: setar o status da feature `15` para `done`.
