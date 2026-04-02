# Tasks — Feature 03: DB Migrations & Seed

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — estrutura de pastas (§3), convenções (§8), TDD obrigatório (§9), regra de seed (§4.1)
- `.specs/features/03_db_migrations_seed/specs.md` — critérios de aceitação desta feature
- `.specs/design.md §1` — schema completo de todas as 13 tabelas (nomes, colunas, tipos, constraints, FKs)
- `.specs/prd.md §3` — catálogo de materiais do mundo padrão (3 materiais, IDs exatos)
- `.specs/prd.md §4` — mundo padrão completo (fábricas, armazéns, lojas, caminhões — valores numéricos exatos)
- `.specs/prd.md §4.1` — mapeamento fábrica → armazéns parceiros com prioridades
- `.specs/features/02_db_models/specs.md` — modelos ORM que esta feature depende (nomes de classes e tabelas)

Não leia specs de features além da 01, 02 e 03. Esta feature não implementa lógica de negócio.

---

## Plano de Execução

Os Grupos 1 e 2 rodam em paralelo — são independentes entre si (testes não dependem da implementação).
O Grupo 3 é sequencial — roda somente após o usuário aprovar os testes do Grupo 1.

---

### Grupo 1 — Testes de Integração (um agente) ⚠ PARE AQUI

**Tarefa:** Escrever todos os testes de integração para migrations e seed. Não implementar produção.

1. Adicionar dependências de teste em `backend/pyproject.toml`:
   - Garantir que `[project.optional-dependencies]` tem o grupo `test` com:
     - `pytest>=8.0`
     - `pytest-asyncio>=0.23`
     - `testcontainers[postgres]>=4.0`

2. Criar `backend/tests/integration/__init__.py` (vazio)

3. Criar `backend/tests/integration/database/__init__.py` (vazio)

4. Criar `backend/tests/conftest.py` (se não existir) com fixtures para testes de integração:
   - Fixture `postgres_container` (scope `session`): instancia `PostgresContainer("postgres:15")` do `testcontainers.postgres`, faz `start()`, e ao final do yield faz `stop()` — sem depender de variável de ambiente
   - Fixture `async_engine` (scope `session`, depende de `postgres_container`): obtém a URL de conexão via `postgres_container.get_connection_url()`, adapta o scheme para `postgresql+asyncpg://`, cria engine com `create_async_engine`
   - Ao iniciar: roda `alembic upgrade head` programaticamente via `alembic.config.Config` + `command.upgrade` apontando para o container
   - Ao encerrar: roda `alembic downgrade base`
   - Fixture `async_session` (scope `function`, depende de `async_engine`): retorna `AsyncSession` conectado a este engine; faz rollback ao encerrar para isolar cada teste

5. Criar `backend/tests/integration/database/test_migrations.py`:
   - `test_all_tables_created`: após `alembic upgrade head`, consulta `information_schema.tables` e verifica que as 13 tabelas existem: `materials`, `factories`, `factory_products`, `factory_partner_warehouses`, `warehouses`, `warehouse_stocks`, `stores`, `store_stocks`, `trucks`, `routes`, `pending_orders`, `events`, `agent_decisions`
   - `test_downgrade_removes_all_tables`: após `alembic downgrade base`, nenhuma das 13 tabelas existe
   - `test_factory_products_composite_pk`: verifica que a tabela `factory_products` tem PK composta sobre (`factory_id`, `material_id`) consultando `information_schema.table_constraints`
   - `test_warehouse_stocks_composite_pk`: análogo para `warehouse_stocks`
   - `test_store_stocks_composite_pk`: análogo para `store_stocks`

6. Criar `backend/tests/integration/database/test_seed.py`:
   - Importa `seed_default_world` de `src.database.seed`
   - `test_materials_count`: após seed, `SELECT COUNT(*) FROM materials` retorna 3
   - `test_materials_ids`: os 3 IDs são exatamente `tijolos`, `vergalhao`, `cimento` — todos `is_active=True`
   - `test_factories_count`: após seed, `SELECT COUNT(*) FROM factories` retorna 3
   - `test_factory_001_values`: `factory-001` tem `name="Tijolaria Anhanguera"`, `lat=-22.9099`, `lng=-47.0626`, `status="operating"`
   - `test_factory_products_factory_001`: produto `tijolos` de `factory-001` tem `stock=12`, `stock_max=30`, `production_rate_max=2`, `production_rate_current=0`, `stock_reserved=0`
   - `test_factory_products_factory_002`: produto `vergalhao` de `factory-002` tem `stock=2000`, `stock_max=5000`, `production_rate_max=120`
   - `test_factory_products_factory_003`: produto `cimento` de `factory-003` tem `stock=400`, `stock_max=750`, `production_rate_max=30`
   - `test_partner_warehouses_count`: `SELECT COUNT(*) FROM factory_partner_warehouses` retorna 7 (2 + 2 + 3)
   - `test_partner_warehouses_priorities`: `factory-001` tem `warehouse-002` com `priority=1` e `warehouse-003` com `priority=2`; `factory-003` tem `warehouse-001` com `priority=1`, `warehouse-002` com `priority=2`, `warehouse-003` com `priority=3`
   - `test_warehouses_count`: após seed, `SELECT COUNT(*) FROM warehouses` retorna 3
   - `test_warehouse_stocks_values`: verifica pelo menos `warehouse-001` com `vergalhao`: `stock=500`, `min_stock=100`; e `warehouse-002` com `cimento`: `stock=150`, `min_stock=25`
   - `test_stores_count`: após seed, `SELECT COUNT(*) FROM stores` retorna 5
   - `test_store_stocks_store_001`: loja `store-001` tem `tijolos` com `stock=1.5`, `demand_rate=0.5`, `reorder_point=1.0`; `vergalhao` com `stock=90`, `demand_rate=30`, `reorder_point=60`; `cimento` com `stock=22.5`, `demand_rate=7.5`, `reorder_point=15`
   - `test_trucks_count`: após seed, `SELECT COUNT(*) FROM trucks` retorna 6
   - `test_trucks_types`: exatamente 3 `truck_type="proprietario"` e 3 `truck_type="terceiro"`
   - `test_truck_001_values`: `truck-001` tem `capacity_tons=15`, `degradation=0.20`, `status="idle"`, `factory_id="factory-001"`, `current_lat=base_lat`
   - `test_truck_004_values`: `truck-004` tem `capacity_tons=18`, `degradation=0.10`, `status="idle"`, `factory_id=None`
   - `test_seed_idempotent`: chamar `seed_default_world` duas vezes sem limpar o banco não duplica registros — counts permanecem 3/3/3/5/6 após a segunda chamada

**⚠ Pare após criar os testes. Não implemente `seed_default_world` nem a migration. Aguarde aprovação do usuário.**

---

### Grupo 2 — Migration Alembic (um agente, paralelo ao Grupo 1)

**Tarefa:** Atualizar `env.py` e gerar a migration inicial.

1. Editar `backend/src/database/migrations/env.py`:
   - Adicionar import: `from src.database.models import Base`
   - Setar `target_metadata = Base.metadata`
   - Garantir suporte async (usar `run_async_migrations` com `asyncpg`) — padrão para `alembic` com SQLAlchemy 2.0 async

2. Gerar a migration inicial:
   - Rodar `alembic -c backend/alembic.ini revision --autogenerate -m "initial_schema"`
   - Verificar que o arquivo gerado em `backend/src/database/migrations/versions/` contém `op.create_table` para todas as 13 tabelas
   - Se a geração automática não estiver disponível no ambiente, criar a migration manualmente com os `op.create_table` e `op.drop_table` corretos baseados em `design.md §1`

3. Verificar os `op.create_table` gerados para garantir:
   - `factory_products` e `factory_partner_warehouses` têm `PrimaryKeyConstraint` composto
   - `warehouse_stocks` e `store_stocks` têm `PrimaryKeyConstraint` composto
   - FKs corretas conforme `design.md §1` — especialmente `trucks.factory_id` com `nullable=True` e `trucks.active_route_id` com `nullable=True`
   - Colunas JSONB (`path`, `timestamps`, `cargo`, `payload`) estão com `sa.JSON` ou `postgresql.JSONB`
   - Defaults: `is_active=True` em `materials`, `stock_reserved=0` em `factory_products` e `warehouse_stocks`, `age_ticks=0` em `pending_orders`

---

### Grupo 3 — Implementação do Seed (um agente, sequencial após aprovação dos testes)

**Tarefa:** Implementar `seed_default_world` em `backend/src/database/seed.py` para que todos os testes do Grupo 1 passem.

1. Implementar `backend/src/database/seed.py` com `async def seed_default_world(session: AsyncSession) -> None`:

   **Materiais** (de `prd.md §3`):
   - `tijolos` / `vergalhao` / `cimento` — todos com `is_active=True`
   - Idempotência: usar `INSERT ... ON CONFLICT (id) DO NOTHING` ou verificar existência antes de inserir

   **Fábricas** (de `prd.md §4`):
   - `factory-001`: `name="Tijolaria Anhanguera"`, `lat=-22.9099`, `lng=-47.0626`, `status="operating"`
   - `factory-002`: `name="Aciaria Sorocabana"`, `lat=-23.5015`, `lng=-47.4526`, `status="operating"`
   - `factory-003`: `name="Cimenteira Paulista"`, `lat=-23.5472`, `lng=-47.4385`, `status="operating"`

   **factory_products** (de `prd.md §4`):
   - `factory-001` / `tijolos`: `stock=12`, `stock_reserved=0`, `stock_max=30`, `production_rate_max=2`, `production_rate_current=0`
   - `factory-002` / `vergalhao`: `stock=2000`, `stock_reserved=0`, `stock_max=5000`, `production_rate_max=120`, `production_rate_current=0`
   - `factory-003` / `cimento`: `stock=400`, `stock_reserved=0`, `stock_max=750`, `production_rate_max=30`, `production_rate_current=0`

   **factory_partner_warehouses** (de `prd.md §4.1`):
   - `factory-001` → `warehouse-002` (priority=1), `warehouse-003` (priority=2)
   - `factory-002` → `warehouse-002` (priority=1), `warehouse-001` (priority=2)
   - `factory-003` → `warehouse-001` (priority=1), `warehouse-002` (priority=2), `warehouse-003` (priority=3)

   **Armazéns** (de `prd.md §4`):
   - `warehouse-001`: `name="Hub Norte"`, `lat=-21.1784`, `lng=-47.8108`, `region="Interior Norte"`, `capacity_total=800`, `status="operating"`
   - `warehouse-002`: `name="Hub Centro-Oeste"`, `lat=-23.1864`, `lng=-46.8964`, `region="Grande SP Oeste"`, `capacity_total=1000`, `status="operating"`
   - `warehouse-003`: `name="Hub Leste"`, `lat=-23.5227`, `lng=-46.1857`, `region="Grande SP Leste"`, `capacity_total=600`, `status="operating"`

   **warehouse_stocks** (de `prd.md §4`):
   - `warehouse-001`: `vergalhao` stock=500/min=100, `cimento` stock=100/min=20 (sem tijolos)
   - `warehouse-002`: `tijolos` stock=10/min=2, `vergalhao` stock=800/min=150, `cimento` stock=150/min=25
   - `warehouse-003`: `tijolos` stock=6/min=1, `vergalhao` stock=400/min=80, `cimento` stock=75/min=15

   **Lojas** (de `prd.md §4`):
   - `store-001`: `name="Constrular Centro"`, `lat=-23.5505`, `lng=-46.6333`, `status="open"`
   - `store-002`: `name="Constrular Zona Leste"`, `lat=-23.5432`, `lng=-46.4506`, `status="open"`
   - `store-003`: `name="Constrular Campinas"`, `lat=-22.9099`, `lng=-47.0626`, `status="open"`
   - `store-004`: `name="Material Norte"`, `lat=-21.1784`, `lng=-47.8108`, `status="open"`
   - `store-005`: `name="Depósito Paulista"`, `lat=-23.4628`, `lng=-46.5333`, `status="open"`

   **store_stocks** (de `prd.md §4`):
   - `store-001`: `tijolos` stock=1.5/rate=0.5/reorder=1.0, `vergalhao` stock=90/rate=30/reorder=60, `cimento` stock=22.5/rate=7.5/reorder=15
   - `store-002`: `tijolos` stock=1.0/rate=0.4/reorder=1.0, `cimento` stock=15/rate=5/reorder=10
   - `store-003`: `tijolos` stock=1.0/rate=0.3/reorder=1.0, `vergalhao` stock=60/rate=20/reorder=40
   - `store-004`: `vergalhao` stock=75/rate=25/reorder=50, `cimento` stock=18/rate=6/reorder=12
   - `store-005`: `tijolos` stock=1.5/rate=0.5/reorder=1.0, `cimento` stock=84/rate=28/reorder=56, `vergalhao` stock=20/rate=6.5/reorder=13

   **Caminhões** (de `prd.md §4`):
   - `truck-001`: `truck_type="proprietario"`, `capacity_tons=15`, `base_lat=-22.9099`, `base_lng=-47.0626`, `current_lat=-22.9099`, `current_lng=-47.0626`, `degradation=0.20`, `breakdown_risk=0.0`, `status="idle"`, `factory_id="factory-001"`, `cargo=None`, `active_route_id=None`
   - `truck-002`: `truck_type="proprietario"`, `capacity_tons=20`, `base_lat=-23.5472`, `base_lng=-47.4385`, `current_lat=-23.5472`, `current_lng=-47.4385`, `degradation=0.15`, `breakdown_risk=0.0`, `status="idle"`, `factory_id="factory-003"`, `cargo=None`, `active_route_id=None`
   - `truck-003`: `truck_type="proprietario"`, `capacity_tons=12`, `base_lat=-23.5015`, `base_lng=-47.4526`, `current_lat=-23.5015`, `current_lng=-47.4526`, `degradation=0.30`, `breakdown_risk=0.0`, `status="idle"`, `factory_id="factory-002"`, `cargo=None`, `active_route_id=None`
   - `truck-004`: `truck_type="terceiro"`, `capacity_tons=18`, `base_lat=-23.5505`, `base_lng=-46.6333`, `current_lat=-23.5505`, `current_lng=-46.6333`, `degradation=0.10`, `breakdown_risk=0.0`, `status="idle"`, `factory_id=None`, `cargo=None`, `active_route_id=None`
   - `truck-005`: `truck_type="terceiro"`, `capacity_tons=22`, `base_lat=-22.9099`, `base_lng=-47.0626`, `current_lat=-22.9099`, `current_lng=-47.0626`, `degradation=0.25`, `breakdown_risk=0.0`, `status="idle"`, `factory_id=None`, `cargo=None`, `active_route_id=None`
   - `truck-006`: `truck_type="terceiro"`, `capacity_tons=10`, `base_lat=-21.1784`, `base_lng=-47.8108`, `current_lat=-21.1784`, `current_lng=-47.8108`, `degradation=0.40`, `breakdown_risk=0.0`, `status="idle"`, `factory_id=None`, `cargo=None`, `active_route_id=None`

2. Rodar `pytest backend/tests/integration/database/` e garantir que todos os testes passam. Corrigir qualquer divergência de valores antes de marcar como concluído.

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes em `backend/tests/integration/database/` passam com `pytest`.
Atualizar `state.md`: setar o status da feature `03` para `done`.
