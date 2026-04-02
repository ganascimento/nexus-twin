# Feature 03 — DB Migrations & Seed

## Objetivo

Criar as migrations Alembic que geram todas as tabelas do PostgreSQL definidas em `design.md §1` e implementar o script de seed que popula o banco com o mundo padrão descrito em `prd.md §4`. Esta feature transforma os modelos ORM da feature 02 em estrutura real no banco e entrega um estado inicial funcional — sem ela, nenhuma feature de repositório ou serviço pode ser testada contra o banco de dados real.

---

## Critérios de Aceitação

### Backend — Migrations

- [ ] `backend/src/database/migrations/env.py` importa `Base` de `src.database.models` e tem `target_metadata = Base.metadata` (atualizado em relação ao stub da feature 01)
- [ ] Existe exatamente uma migration inicial em `backend/src/database/migrations/versions/` gerada via `alembic revision --autogenerate`
- [ ] `alembic upgrade head` aplicado num banco PostgreSQL vazio cria as seguintes tabelas: `materials`, `factories`, `factory_products`, `factory_partner_warehouses`, `warehouses`, `warehouse_stocks`, `stores`, `store_stocks`, `trucks`, `routes`, `pending_orders`, `events`, `agent_decisions`
- [ ] `alembic downgrade base` desfaz a migration sem erros — todas as 13 tabelas são removidas
- [ ] A migration não usa tipos PostGIS — colunas de posição são `FLOAT` e colunas de path são `JSONB`, conforme `design.md §1`
- [ ] PKs compostas de `factory_products`, `factory_partner_warehouses`, `warehouse_stocks` e `store_stocks` estão corretas na migration gerada
- [ ] FKs estão presentes: `factory_products.factory_id → factories.id`, `factory_products.material_id → materials.id`, `factory_partner_warehouses.factory_id → factories.id`, `factory_partner_warehouses.warehouse_id → warehouses.id`, `warehouse_stocks.warehouse_id → warehouses.id`, `warehouse_stocks.material_id → materials.id`, `store_stocks.store_id → stores.id`, `store_stocks.material_id → materials.id`, `trucks.factory_id → factories.id` (nullable), `trucks.active_route_id → routes.id` (nullable), `routes.truck_id → trucks.id`

### Backend — Seed

- [ ] `backend/src/database/seed.py` expõe uma função `async def seed_default_world(session: AsyncSession) -> None` idempotente — se os registros já existem (verificado pelo `id`), a função não duplica dados
- [ ] Após executar `seed_default_world`, o banco contém exatamente os 3 materiais de `prd.md §3`: `tijolos`, `vergalhao`, `cimento` — todos com `is_active=True`
- [ ] Após executar `seed_default_world`, o banco contém exatamente as 3 fábricas de `prd.md §4` com os valores corretos:
  - `factory-001`: `name="Tijolaria Anhanguera"`, `lat=-22.9099`, `lng=-47.0626`, `status="operating"`
  - `factory-002`: `name="Aciaria Sorocabana"`, `lat=-23.5015`, `lng=-47.4526`, `status="operating"`
  - `factory-003`: `name="Cimenteira Paulista"`, `lat=-23.5472`, `lng=-47.4385`, `status="operating"`
- [ ] `factory_products` contém os produtos das fábricas com os valores corretos de `prd.md §4` (estoque inicial, produção máx/tick, estoque máximo)
- [ ] `factory_partner_warehouses` contém os vínculos de `prd.md §4.1` com as prioridades corretas:
  - `factory-001` → `warehouse-002` (priority 1), `warehouse-003` (priority 2)
  - `factory-002` → `warehouse-002` (priority 1), `warehouse-001` (priority 2)
  - `factory-003` → `warehouse-001` (priority 1), `warehouse-002` (priority 2), `warehouse-003` (priority 3)
- [ ] Após executar `seed_default_world`, o banco contém exatamente os 3 armazéns de `prd.md §4` com os valores corretos de localização, `capacity_total`, `region` e `status="operating"`
- [ ] `warehouse_stocks` contém os estoques iniciais e `min_stock` por material por armazém conforme `prd.md §4`
- [ ] Após executar `seed_default_world`, o banco contém exatamente as 5 lojas de `prd.md §4` com os valores corretos de localização e `status="open"`
- [ ] `store_stocks` contém os estoques iniciais, `demand_rate` e `reorder_point` por material por loja conforme `prd.md §4`
- [ ] Após executar `seed_default_world`, o banco contém exatamente os 6 caminhões de `prd.md §4` com os valores corretos de `truck_type`, `capacity_tons`, `degradation`, `status="idle"`, `factory_id` (nullable para terceiros) e posição inicial igual à base
- [ ] `backend/src/database/seed.py` é chamado pelo entry point de setup do banco (via `alembic upgrade head && python -m src.database.seed` ou endpoint `POST /admin/seed` — a escolha de invocação pode ser feita na feature 01/13, mas a função deve ser invocável de forma isolada)

### Testes

- [ ] `backend/tests/integration/database/test_migrations.py` verifica que `alembic upgrade head` cria todas as 13 tabelas esperadas num banco PostgreSQL de teste real
- [ ] `backend/tests/integration/database/test_seed.py` verifica:
  - Após `seed_default_world`, existem 3 materiais, 3 fábricas, 3 armazéns, 5 lojas e 6 caminhões
  - Os valores numéricos críticos estão corretos (ex: `factory-001` tijolos `stock=12`, `stock_max=30`, `production_rate_max=2`)
  - Chamar `seed_default_world` duas vezes não duplica registros
  - Os 6 vínculos `factory_partner_warehouses` existem com as prioridades corretas
- [ ] Testes de integração passam com `pytest backend/tests/integration/database/` usando banco PostgreSQL real (não mock)

---

## Fora do Escopo

- Definição dos modelos SQLAlchemy ORM — coberto pela feature 02
- Queries e lógica de repositório sobre as tabelas — coberto pela feature 04
- Endpoint REST para seed ou qualquer rota de admin além da invocação direta da função — coberto pela feature 13
- Migrations futuras (para novas colunas ou tabelas adicionadas em features posteriores) — cada feature que alterar o schema cria sua própria migration
- Lógica de negócio de qualquer entidade (cálculos de estoque, decisões de agente) — coberto pelas features 06–12
- Tipos PostGIS / extensão espacial — não é usada no schema (rotas são JSONB simples)
