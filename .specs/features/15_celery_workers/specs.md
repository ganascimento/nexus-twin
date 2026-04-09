# Feature 15 — Celery Workers

## Objetivo

Implementar a infraestrutura Celery para jobs de background nao-LLM: geracao de relatorios de eficiencia, sumarizacao de decisoes por periodo e exportacao de dados historicos. Os workers rodam em processo separado do FastAPI com broker e backend Redis. Esta feature entrega as tasks definidas em `design.md §4` e os endpoints REST para aciona-las de forma assincrona (retornando `task_id` para consulta posterior).

---

## Criterios de Aceitacao

### Backend — Infraestrutura Celery

- [ ] `workers/celery_app.py` configura instancia Celery com `broker=REDIS_URL` e `backend=REDIS_URL` (lidos do ambiente)
- [ ] Worker inicializavel via `celery -A src.workers.celery_app worker`
- [ ] Celery `autodiscover_tasks` encontra as tasks em `src.workers.tasks`
- [ ] Serializacao configurada como JSON (`task_serializer`, `result_serializer`, `accept_content`)
- [ ] Sessao de banco de dados sincrona (`sessionmaker` + `create_engine`) disponivel para as tasks — Celery roda fora do event loop async; `DATABASE_URL` convertida de `postgresql+asyncpg://` para `postgresql://` automaticamente

### Backend — Tasks de Relatorio (`workers/tasks/reports.py`)

- [ ] `generate_efficiency_report` (conforme `design.md §4`) retorna dict com:
  - `orders_delivered`: contagem de pedidos com status `delivered`
  - `orders_late`: contagem de pedidos onde `age_ticks` no momento da entrega excedeu `eta_ticks`
  - `stock_ruptures`: lista de `{entity_type, entity_id, material_id}` para entidades com `stock = 0` em algum produto
  - `truck_utilization`: dict por `truck_id` com `{in_transit_ticks, idle_ticks, utilization_pct}`
- [ ] `generate_decision_summary` (conforme `design.md §4`) recebe `tick_start` e `tick_end` opcionais (padrao: ultimos 24 ticks) e retorna dict com decisoes agrupadas por `agent_type` e `action`, contando ocorrencias

### Backend — Tasks de Exportacao (`workers/tasks/exports.py`)

- [ ] `export_decision_history` aceita filtros opcionais (`entity_id`, `limit`) e retorna lista serializada de registros de `agent_decisions` em formato dict (conforme `design.md §4`)
- [ ] `export_event_history` retorna lista serializada de todos os registros de `events` com status de resolucao (`active`/`resolved`), `tick_start`, `tick_end`
- [ ] `export_world_snapshot` retorna o `WorldState` atual serializado como dict JSON — factories com produtos, warehouses com stocks, stores com stocks, trucks com posicao e carga

### Backend — Endpoints REST

- [ ] `POST /api/v1/reports/efficiency` aciona `generate_efficiency_report.delay()` e retorna `202` com `{ "task_id": "..." }`
- [ ] `POST /api/v1/reports/decisions` aciona `generate_decision_summary.delay()` com parametro opcional `ticks` (padrao: 24); retorna `202` com `task_id`
- [ ] `POST /api/v1/exports/decisions` aciona `export_decision_history.delay()` com filtros opcionais `entity_id` e `limit`; retorna `202` com `task_id`
- [ ] `POST /api/v1/exports/events` aciona `export_event_history.delay()`; retorna `202` com `task_id`
- [ ] `POST /api/v1/exports/world-snapshot` aciona `export_world_snapshot.delay()`; retorna `202` com `task_id`
- [ ] `GET /api/v1/tasks/{task_id}/status` retorna estado da task Celery (`PENDING`, `STARTED`, `SUCCESS`, `FAILURE`) e o `result` quando `SUCCESS`

---

## Fora do Escopo

- Paralelismo de agentes LLM — usa `asyncio.create_task`, nao Celery (`CLAUDE.md §4.4`)
- WebSocket — feature 14
- Frontend dashboard — features 16-18
- Agendamento automatico de `generate_decision_summary` pelo engine a cada 24 ticks — sera integrado quando o engine estiver em producao; por ora, apenas o endpoint REST
- Armazenamento persistente de exports em filesystem — exports retornam dados diretamente no resultado da task Celery
- Celery Beat (scheduler periodico) — fora do escopo desta feature
