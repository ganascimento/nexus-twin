# Feature 13 — API REST

## Objetivo

Implementar todos os endpoints HTTP REST definidos em `design.md §2`, expondo a camada de services para o frontend e ferramentas externas. Esta feature transforma o backend de um conjunto de services internos em uma API consumível, cobrindo: controle da simulação, leitura do estado do mundo, CRUD de materiais, CRUD de entidades (fábricas, armazéns, lojas, caminhões), ajuste manual de estoque, injeção/resolução de caos, e leitura de decisões dos agentes.

Todos os endpoints vivem em `backend/src/api/routes/` e usam os services da camada `backend/src/services/` via FastAPI Depends. A API não contém lógica de negócio — apenas validação de entrada (Pydantic schemas), chamada ao service e serialização de resposta.

---

## Critérios de Aceitação

### Simulação — `routes/simulation.py`

- [ ] `POST /api/v1/simulation/start` → chama `SimulationService.start()`, retorna `200`
- [ ] `POST /api/v1/simulation/stop` → chama `SimulationService.stop()`, retorna `200`
- [ ] `POST /api/v1/simulation/tick` → chama `SimulationService.advance_tick()`, retorna `200` com o `WorldState` resultante; retorna `409` se simulação está rodando
- [ ] `GET /api/v1/simulation/status` → retorna `SimulationStatus` (running/stopped, tick atual, intervalo, timestamp simulado)
- [ ] `PATCH /api/v1/simulation/speed` → chama `SimulationService.set_tick_interval()`, retorna `400` se valor < 10

### Estado do Mundo — `routes/world.py`

- [ ] `GET /api/v1/world/snapshot` → retorna `WorldStatePayload` completo via `WorldStateService.get_snapshot()`
- [ ] `GET /api/v1/world/tick` → retorna tick atual e timestamp simulado

### Materiais — `routes/materials.py`

- [ ] `GET /api/v1/materials` → lista materiais, aceita query param `?active_only=true`
- [ ] `POST /api/v1/materials` → cria material, retorna `201`
- [ ] `PATCH /api/v1/materials/{id}` → edita nome, retorna `200`; `404` se não existe
- [ ] `PATCH /api/v1/materials/{id}/deactivate` → desativa material, retorna `200`; `409` se há entidades vinculadas

### Fábricas — `routes/factories.py`

- [ ] `GET /api/v1/entities/factories` → lista fábricas com estoque e status
- [ ] `GET /api/v1/entities/factories/{id}` → detalhe com produtos, caminhões, ordens; `404` se não existe
- [ ] `POST /api/v1/entities/factories` → cria fábrica, retorna `201`
- [ ] `PATCH /api/v1/entities/factories/{id}` → edita materiais, capacidades, parceiros; `404` se não existe
- [ ] `DELETE /api/v1/entities/factories/{id}` → remove fábrica (cascade de pedidos conforme design.md §10.4); `404` se não existe
- [ ] `PATCH /api/v1/entities/factories/{id}/stock` → ajusta estoque manual por produto; `404` se fábrica ou produto não existe

### Armazéns — `routes/warehouses.py`

- [ ] `GET /api/v1/entities/warehouses` → lista armazéns com estoque
- [ ] `GET /api/v1/entities/warehouses/{id}` → detalhe; `404` se não existe
- [ ] `POST /api/v1/entities/warehouses` → cria armazém, retorna `201`
- [ ] `PATCH /api/v1/entities/warehouses/{id}` → edita materiais, capacidades, mínimos; `404` se não existe
- [ ] `DELETE /api/v1/entities/warehouses/{id}` → remove armazém (cascade de pedidos); `404` se não existe
- [ ] `PATCH /api/v1/entities/warehouses/{id}/stock` → ajusta estoque manual; `404` se armazém ou produto não existe

### Lojas — `routes/stores.py`

- [ ] `GET /api/v1/entities/stores` → lista lojas com estoque
- [ ] `GET /api/v1/entities/stores/{id}` → detalhe; `404` se não existe
- [ ] `POST /api/v1/entities/stores` → cria loja, retorna `201`
- [ ] `PATCH /api/v1/entities/stores/{id}` → edita materiais, demanda, reorder points; `404` se não existe
- [ ] `DELETE /api/v1/entities/stores/{id}` → remove loja (cancela pedidos emitidos); `404` se não existe
- [ ] `PATCH /api/v1/entities/stores/{id}/stock` → ajusta estoque manual; `404` se loja ou produto não existe

### Caminhões — `routes/trucks.py`

- [ ] `GET /api/v1/entities/trucks` → lista caminhões com posição, carga, degradação
- [ ] `GET /api/v1/entities/trucks/{id}` → detalhe com rota ativa e histórico; `404` se não existe
- [ ] `POST /api/v1/entities/trucks` → cria caminhão (proprietário ou terceiro), retorna `201`
- [ ] `DELETE /api/v1/entities/trucks/{id}` → remove caminhão (reassinalação se em trânsito); `404` se não existe

### Caos — `routes/chaos.py`

- [ ] `GET /api/v1/chaos/events` → lista eventos de caos ativos via `ChaosService.list_active_events()`
- [ ] `POST /api/v1/chaos/events` → injeta evento manual via `ChaosService.inject_event()`, retorna `201`
- [ ] `POST /api/v1/chaos/events/{id}/resolve` → resolve evento via `ChaosService.resolve_event()`; `404` se não existe; `409` se já resolvido

### Decisões — `routes/decisions.py`

- [ ] `GET /api/v1/decisions` → lista decisões recentes, aceita `?entity_id=` e `?limit=`
- [ ] `GET /api/v1/decisions/{entity_id}` → histórico de decisões de uma entidade; `404` se entidade não existe

### Geral

- [ ] Todos os endpoints registrados no app FastAPI via `APIRouter` com prefixo `/api/v1`
- [ ] Schemas Pydantic de request/response definidos em `api/models/` — um arquivo por domínio, separados das rotas
- [ ] Erros de validação retornam `422` automaticamente (comportamento padrão do FastAPI)
- [ ] Services injetados via `Depends(get_<service>)` — sem instanciação direta nos handlers

### Testes

- [ ] Testes unitários para cada arquivo de rotas em `backend/tests/unit/api/routes/`
- [ ] Testes usam `httpx.AsyncClient` com `ASGITransport` (sem servidor real)
- [ ] Services mockados via `app.dependency_overrides`
- [ ] Cada endpoint testado para cenário de sucesso e cenários de erro relevantes (`404`, `409`, `400`)

---

## Fora do Escopo

- WebSocket streaming (`/ws`) — feature 14 (`api_websocket`)
- Celery workers e tasks de relatório/exportação — feature 15 (`celery_workers`)
- Lógica de negócio dentro dos handlers — toda lógica está nos services (features 06, 07, 12)
- Autenticação/autorização — não planejada nesta fase do projeto
- Rate limiting nos endpoints REST — limitação está apenas no `asyncio.Semaphore` dos agentes
