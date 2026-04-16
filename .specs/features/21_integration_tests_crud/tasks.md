# Tasks — Feature 21: Integration Tests CRUD

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — estrutura de pastas (S3), convencoes (S8), TDD (S9)
- `.specs/features/21_integration_tests_crud/specs.md` — criterios de aceitacao
- `.specs/design.md` S2 — endpoints HTTP com paths e metodos exatos
- `backend/tests/conftest.py` — fixtures existentes (postgres_container, async_session, seeded_db)
- `backend/tests/integration/database/test_seed.py` — exemplo de teste de integracao existente
- `backend/src/api/routes/*.py` — rotas que serao testadas
- `backend/src/api/dependencies.py` — dependency factories para override

---

## Plano de Execucao

Feature com TDD **invertido** (os testes SAO o entregavel). Nao ha fase de implementacao separada — os testes validam codigo ja existente.

Execucao em 3 grupos sequenciais. Subagentes dentro de cada grupo podem rodar em paralelo.

---

### Grupo 1 — Infraestrutura de Teste

#### Tarefa 1.1 — Conftest de integracao

**Arquivo:** `backend/tests/integration/conftest.py`

Criar fixtures compartilhadas para todos os testes de integracao CRUD:

1. Fixture `client` (function-scope):
   - Cria `httpx.AsyncClient` com `ASGITransport(app=app)`
   - Override `get_db` para retornar a `async_session` do testcontainer
   - Limpa `app.dependency_overrides` no teardown
   - Base URL: `http://test`

2. Fixture `seeded_session` (function-scope):
   - Combina `async_session` + seed dos dados default
   - Garante que cada teste comeca com o mundo padrao populado

3. Fixture `clean_session` (function-scope):
   - Apenas `async_session` sem seed — para testes que criam dados do zero

4. Criar `backend/tests/integration/crud/__init__.py`

**Cuidados:**
- Importar `app` de `src.main` — garantir que `load_dotenv` nao interfere (o `DATABASE_URL` vem do override)
- Override de `get_db` deve usar `yield session` sem commit/rollback (o conftest raiz ja gerencia)
- Nao criar novo container — reutilizar o do conftest raiz

---

### Grupo 2 — Testes CRUD por Entidade (parallelizaveis)

Cada subagente cria um arquivo de teste independente. Podem rodar em paralelo.

#### Subagente 2A — Materials

**Arquivo:** `backend/tests/integration/crud/test_materials_integration.py`

Testes (todos usam fixture `client` + `clean_session`):

1. `test_create_material` — POST, verifica response 201 e campos
2. `test_create_material_persists_in_db` — POST, depois SELECT no banco para confirmar
3. `test_list_materials` — cria 2, GET lista, verifica contagem
4. `test_list_materials_active_only` — cria 2, desativa 1, GET com ?active_only=true
5. `test_update_material_name` — POST + PATCH, verifica novo nome na response
6. `test_update_material_persists_in_db` — PATCH, depois SELECT para confirmar
7. `test_update_material_not_found` — PATCH com id inexistente, verifica 404
8. `test_deactivate_material` — POST + PATCH deactivate, verifica is_active=False
9. `test_deactivate_material_persists_in_db` — PATCH deactivate, SELECT para confirmar

#### Subagente 2B — Factories

**Arquivo:** `backend/tests/integration/crud/test_factories_integration.py`

Testes (usam `client` + `clean_session`; os que precisam de material criam um via API primeiro):

1. `test_create_factory` — POST com name/lat/lng, verifica 201
2. `test_create_factory_persists_in_db` — POST, SELECT no banco
3. `test_list_factories` — cria 2, GET, verifica contagem
4. `test_get_factory_by_id` — POST + GET por id, verifica campos
5. `test_get_factory_not_found` — GET com id inexistente, 404
6. `test_update_factory` — POST + PATCH, verifica campos atualizados
7. `test_update_factory_persists_in_db` — PATCH, SELECT no banco
8. `test_delete_factory` — POST + DELETE, verifica 200
9. `test_delete_factory_removes_from_db` — DELETE, SELECT retorna None
10. `test_delete_factory_not_found` — DELETE com id inexistente, 404
11. `test_adjust_factory_stock` — cria factory + product, PATCH stock com delta, verifica response
12. `test_adjust_factory_stock_persists_in_db` — PATCH stock, SELECT confirma delta

#### Subagente 2C — Warehouses

**Arquivo:** `backend/tests/integration/crud/test_warehouses_integration.py`

Mesma estrutura do 2B adaptada para warehouses:

1. `test_create_warehouse` — POST com name/lat/lng/region/capacity_total, 201
2. `test_create_warehouse_persists_in_db` — SELECT confirma
3. `test_list_warehouses` — cria 2, GET, contagem
4. `test_get_warehouse_by_id` — verifica campos
5. `test_update_warehouse` — PATCH, verifica
6. `test_update_warehouse_persists_in_db` — SELECT confirma
7. `test_delete_warehouse` — DELETE, 200
8. `test_delete_warehouse_removes_from_db` — SELECT retorna None
9. `test_adjust_warehouse_stock` — cria + stock, PATCH delta, verifica
10. `test_adjust_warehouse_stock_persists_in_db` — SELECT confirma

#### Subagente 2D — Stores

**Arquivo:** `backend/tests/integration/crud/test_stores_integration.py`

1. `test_create_store` — POST com name/lat/lng, 201
2. `test_create_store_persists_in_db`
3. `test_list_stores`
4. `test_get_store_by_id`
5. `test_update_store`
6. `test_update_store_persists_in_db`
7. `test_delete_store`
8. `test_delete_store_removes_from_db`

#### Subagente 2E — Trucks

**Arquivo:** `backend/tests/integration/crud/test_trucks_integration.py`

1. `test_create_truck` — POST com truck_type/capacity_tons/lat/lng, 201
2. `test_create_truck_persists_in_db`
3. `test_list_trucks`
4. `test_get_truck_by_id`
5. `test_delete_truck`
6. `test_delete_truck_removes_from_db`

---

### Grupo 3 — Testes Transversais

#### Subagente 3A — World Snapshot

**Arquivo:** `backend/tests/integration/crud/test_world_snapshot_integration.py`

Testes (usam `client` + `seeded_session`):

1. `test_snapshot_returns_all_seeded_factories` — GET /world/snapshot, verifica 3 factories
2. `test_snapshot_returns_all_seeded_warehouses` — verifica 3 warehouses
3. `test_snapshot_returns_all_seeded_stores` — verifica 5 stores
4. `test_snapshot_returns_all_seeded_trucks` — verifica 6 trucks
5. `test_snapshot_contains_factory_products` — verifica que cada factory tem products aninhados
6. `test_snapshot_contains_warehouse_stocks` — verifica stocks aninhados
7. `test_snapshot_contains_store_stocks` — verifica stocks aninhados
8. `test_snapshot_factory_coordinates` — verifica lat/lng de factory-001

#### Subagente 3B — Cross-Entity

**Arquivo:** `backend/tests/integration/crud/test_cross_entity_integration.py`

Testes (usam `client` + `clean_session`):

1. `test_create_factory_with_product` — cria material, cria factory com product vinculado, verifica factory_products no banco
2. `test_create_warehouse_with_stock` — cria material, cria warehouse com stock, verifica warehouse_stocks no banco
3. `test_create_store_with_stock` — cria material, cria store com stock, verifica store_stocks no banco
4. `test_delete_factory_orphans_truck` — cria factory, cria truck proprietario vinculado, deleta factory, verifica truck.factory_id = None

---

## Observacoes

- **Nao criar mocks** — estes sao testes de integracao, tudo bate no banco real
- **Unica excecao:** Redis (publisher) pode ser mockado se necessario para evitar dependencia extra
- **Cada teste deve ser independente** — nao depender da ordem de execucao
- **Assertions duplas:** cada operacao de escrita valida (1) a response HTTP E (2) o estado no banco
- **Usar `select()` do SQLAlchemy** para assertions de banco, nao chamar endpoints GET para verificar
