# Feature 21 — Integration Tests: Entity CRUD

## Objetivo

Implementar testes de integração que validam o ciclo completo de CRUD (Create, Read, Update, Delete) de todas as entidades do sistema contra um banco PostgreSQL real (via testcontainers). Cada teste executa a operação via API HTTP (FastAPI + httpx AsyncClient), verifica a resposta e depois consulta o banco diretamente para confirmar que a persistência ocorreu corretamente.

Diferente dos testes unitários existentes (que mockam repositories e services), estes testes **atravessam todas as camadas**: HTTP request → rota → dependency injection → service → repository → PostgreSQL real → response. Isso garante que migrations, ORM models, repositories, services e rotas estão integrados corretamente.

---

## Escopo

### Entidades cobertas

1. **Materials** — CRUD completo + deactivate
2. **Factories** — Create, Read, Update, Delete + stock adjust
3. **Warehouses** — Create, Read, Update, Delete + stock adjust
4. **Stores** — Create, Read, Update, Delete + stock adjust
5. **Trucks** — Create, Read, Delete

### O que NÃO está no escopo

- Testes de simulação (feature 22)
- Testes de agentes/LLM (feature 22)
- Testes de WebSocket (já cobertos em unit tests)
- Testes de Celery workers (não requerem banco)

---

## Infraestrutura de Teste

### PostgreSQL via testcontainers

Todos os testes usam a infraestrutura existente em `tests/conftest.py`:
- `postgres_container` (session-scope) — container PostgreSQL 15 efêmero
- `async_engine` (session-scope) — engine com migrations aplicadas
- `async_session` (function-scope) — sessão com rollback automático por teste

### Cliente HTTP

Cada módulo de teste cria um `httpx.AsyncClient` com `ASGITransport(app=app)` para testar a API in-process. A dependency `get_db` é substituída via `app.dependency_overrides` para injetar a `async_session` do testcontainer, garantindo que API e assertions leem/escrevem no mesmo banco.

### Isolamento

Cada teste roda em uma transação que é revertida ao final — testes não interferem entre si.

---

## Critrios de Aceitao

### Materials — `test_materials_integration.py`

- [ ] `POST /api/v1/materials` → cria material, retorna 201 com `id`, `name`, `is_active=True`
- [ ] `POST /api/v1/materials` → confirma no banco que o material foi persistido com os valores corretos
- [ ] `GET /api/v1/materials` → retorna lista contendo o material criado
- [ ] `GET /api/v1/materials?active_only=true` → filtra apenas materiais ativos
- [ ] `PATCH /api/v1/materials/{id}` → atualiza nome, retorna 200 com nome novo
- [ ] `PATCH /api/v1/materials/{id}` → confirma no banco que o nome foi atualizado
- [ ] `PATCH /api/v1/materials/{id}` → retorna 404 para id inexistente
- [ ] `PATCH /api/v1/materials/{id}/deactivate` → desativa material, retorna 200 com `is_active=False`
- [ ] `PATCH /api/v1/materials/{id}/deactivate` → confirma no banco que `is_active=False`

### Factories — `test_factories_integration.py`

- [ ] `POST /api/v1/entities/factories` → cria fábrica com name/lat/lng, retorna 201
- [ ] `POST /api/v1/entities/factories` → confirma no banco que factory foi criada com coordenadas corretas
- [ ] `GET /api/v1/entities/factories` → retorna lista contendo a fábrica criada
- [ ] `GET /api/v1/entities/factories/{id}` → retorna fábrica com dados corretos
- [ ] `GET /api/v1/entities/factories/{id}` → retorna 404 para id inexistente
- [ ] `PATCH /api/v1/entities/factories/{id}` → atualiza nome/status, retorna 200
- [ ] `PATCH /api/v1/entities/factories/{id}` → confirma no banco que os campos foram atualizados
- [ ] `DELETE /api/v1/entities/factories/{id}` → remove fábrica, retorna 200
- [ ] `DELETE /api/v1/entities/factories/{id}` → confirma no banco que a factory não existe mais
- [ ] `DELETE /api/v1/entities/factories/{id}` → retorna 404 para id inexistente
- [ ] `PATCH /api/v1/entities/factories/{id}/stock` → ajusta estoque de um produto, retorna 200
- [ ] `PATCH /api/v1/entities/factories/{id}/stock` → confirma no banco que o estoque mudou pelo delta correto

### Warehouses — `test_warehouses_integration.py`

- [ ] `POST /api/v1/entities/warehouses` → cria armazém com name/lat/lng/region/capacity_total, retorna 201
- [ ] `POST /api/v1/entities/warehouses` → confirma no banco que warehouse foi criado
- [ ] `GET /api/v1/entities/warehouses` → retorna lista contendo o armazém criado
- [ ] `GET /api/v1/entities/warehouses/{id}` → retorna armazém com dados corretos
- [ ] `PATCH /api/v1/entities/warehouses/{id}` → atualiza campos, confirma no banco
- [ ] `DELETE /api/v1/entities/warehouses/{id}` → remove armazém, confirma no banco
- [ ] `PATCH /api/v1/entities/warehouses/{id}/stock` → ajusta estoque, confirma delta no banco

### Stores — `test_stores_integration.py`

- [ ] `POST /api/v1/entities/stores` → cria loja com name/lat/lng, retorna 201
- [ ] `POST /api/v1/entities/stores` → confirma no banco que store foi criada
- [ ] `GET /api/v1/entities/stores` → retorna lista contendo a loja criada
- [ ] `GET /api/v1/entities/stores/{id}` → retorna loja com dados corretos
- [ ] `PATCH /api/v1/entities/stores/{id}` → atualiza campos, confirma no banco
- [ ] `DELETE /api/v1/entities/stores/{id}` → remove loja, confirma no banco

### Trucks — `test_trucks_integration.py`

- [ ] `POST /api/v1/entities/trucks` → cria caminhão com truck_type/capacity/lat/lng, retorna 201
- [ ] `POST /api/v1/entities/trucks` → confirma no banco que truck foi criado com campos corretos
- [ ] `GET /api/v1/entities/trucks` → retorna lista contendo o caminhão criado
- [ ] `GET /api/v1/entities/trucks/{id}` → retorna caminhão com dados corretos
- [ ] `DELETE /api/v1/entities/trucks/{id}` → remove caminhão, confirma no banco

### World Snapshot — `test_world_snapshot_integration.py`

- [ ] `GET /api/v1/world/snapshot` → retorna WorldState com todas as entidades do seed
- [ ] Snapshot contém factories, warehouses, stores, trucks com contagens corretas
- [ ] Snapshot contém products/stocks aninhados corretamente em cada entidade

### Cross-Entity — `test_cross_entity_integration.py`

- [ ] Criar material → criar fábrica com product desse material → verificar que factory_products foi criado
- [ ] Criar material → criar warehouse com stock desse material → verificar que warehouse_stocks foi criado
- [ ] Criar material → criar store com stock desse material → verificar que store_stocks foi criado
- [ ] Deletar fábrica com caminhão proprietário → verificar que caminhão ficou sem factory_id

---

## Estrutura de Arquivos

```
backend/tests/integration/
├── conftest.py                          # Fixtures compartilhadas (client, db override)
├── crud/
│   ├── __init__.py
│   ├── test_materials_integration.py
│   ├── test_factories_integration.py
│   ├── test_warehouses_integration.py
│   ├── test_stores_integration.py
│   ├── test_trucks_integration.py
│   ├── test_world_snapshot_integration.py
│   └── test_cross_entity_integration.py
└── database/
    ├── test_migrations.py               # Já existente
    └── test_seed.py                     # Já existente
```
