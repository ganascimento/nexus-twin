# Feature 02 — DB Models

## Objetivo

Implementar todos os modelos SQLAlchemy ORM que mapeiam as tabelas do PostgreSQL definidas em `design.md §1`. Esta feature entrega a camada de persistência tipada do sistema — sem ela, nenhuma feature de repositório, serviço ou migração pode avançar. O `alembic` também precisa dos modelos para gerar as migrations automaticamente na feature 03.

---

## Critérios de Aceitação

### Backend — Modelos

- [ ] `backend/src/database/models/material.py` define `Material` mapeando a tabela `materials` com colunas: `id` (VARCHAR(50), PK), `name` (VARCHAR(100), NOT NULL), `is_active` (BOOLEAN, NOT NULL, DEFAULT True), `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT now)
- [ ] `backend/src/database/models/factory.py` define `Factory`, `FactoryProduct` e `FactoryPartnerWarehouse`:
  - `Factory`: colunas `id`, `name`, `lat`, `lng`, `status` (VARCHAR(20), NOT NULL), `created_at`, `updated_at`
  - `FactoryProduct`: PK composta (`factory_id`, `material_id`), colunas `stock`, `stock_reserved` (DEFAULT 0), `stock_max`, `production_rate_max`, `production_rate_current` — todos FLOAT, NOT NULL
  - `FactoryPartnerWarehouse`: PK composta (`factory_id`, `warehouse_id`), coluna `priority` (INTEGER, NOT NULL)
- [ ] `backend/src/database/models/warehouse.py` define `Warehouse` e `WarehouseStock`:
  - `Warehouse`: colunas `id`, `name`, `lat`, `lng`, `region` (VARCHAR(100)), `capacity_total` (FLOAT), `status` (VARCHAR(20)), `created_at`, `updated_at`
  - `WarehouseStock`: PK composta (`warehouse_id`, `material_id`), colunas `stock`, `stock_reserved` (DEFAULT 0), `min_stock` — todos FLOAT, NOT NULL
- [ ] `backend/src/database/models/store.py` define `Store` e `StoreStock`:
  - `Store`: colunas `id`, `name`, `lat`, `lng`, `status` (VARCHAR(20)), `created_at`, `updated_at`
  - `StoreStock`: PK composta (`store_id`, `material_id`), colunas `stock`, `demand_rate`, `reorder_point` — todos FLOAT, NOT NULL
- [ ] `backend/src/database/models/truck.py` define `Truck` com todas as colunas: `id` (VARCHAR(50), PK), `truck_type` (VARCHAR(20), NOT NULL — `proprietario` ou `terceiro`), `capacity_tons` (FLOAT), `base_lat`, `base_lng`, `current_lat`, `current_lng` (FLOAT), `degradation` (FLOAT, NOT NULL — 0.0–1.0), `breakdown_risk` (FLOAT, NOT NULL), `status` (VARCHAR(20), NOT NULL — `idle`/`evaluating`/`in_transit`/`broken`/`maintenance`), `factory_id` (FK→factories, nullable), `cargo` (JSONB, nullable), `active_route_id` (FK→routes, nullable), `created_at`, `updated_at`
- [ ] `backend/src/database/models/route.py` define `Route` com: `id` (UUID, PK), `truck_id` (FK→trucks), `origin_type` (VARCHAR(20)), `origin_id` (VARCHAR(50)), `dest_type` (VARCHAR(20)), `dest_id` (VARCHAR(50)), `path` (JSONB, NOT NULL), `timestamps` (JSONB, NOT NULL), `eta_ticks` (INTEGER, NOT NULL), `status` (VARCHAR(20), NOT NULL — `active`/`completed`/`interrupted`), `started_at` (TIMESTAMPTZ, NOT NULL), `completed_at` (TIMESTAMPTZ, nullable)
- [ ] `backend/src/database/models/order.py` define `PendingOrder` com: `id` (UUID, PK), `requester_type` (VARCHAR(20)), `requester_id` (VARCHAR(50)), `target_type` (VARCHAR(20)), `target_id` (VARCHAR(50)), `material_id` (FK→materials), `quantity_tons` (FLOAT), `status` (VARCHAR(20), NOT NULL — `pending`/`confirmed`/`rejected`/`delivered`/`cancelled`), `age_ticks` (INTEGER, NOT NULL, DEFAULT 0), `retry_after_tick` (INTEGER, nullable), `rejection_reason` (TEXT, nullable), `cancellation_reason` (TEXT, nullable), `eta_ticks` (INTEGER, nullable), `created_at`, `updated_at`
- [ ] `backend/src/database/models/event.py` define `ChaosEvent` com: `id` (UUID, PK), `event_type` (VARCHAR(50), NOT NULL), `source` (VARCHAR(20), NOT NULL — `user`/`master_agent`/`engine`), `entity_type` (VARCHAR(20), nullable), `entity_id` (VARCHAR(50), nullable), `payload` (JSONB, NOT NULL), `status` (VARCHAR(20), NOT NULL — `active`/`resolved`), `tick_start` (INTEGER, NOT NULL), `tick_end` (INTEGER, nullable), `created_at` (TIMESTAMPTZ, NOT NULL)
- [ ] `backend/src/database/models/agent_decision.py` define `AgentDecision` com: `id` (UUID, PK), `agent_type` (VARCHAR(20), NOT NULL — `factory`/`warehouse`/`store`/`truck`/`master`), `entity_id` (VARCHAR(50), NOT NULL), `tick` (INTEGER, NOT NULL), `event_type` (VARCHAR(50), NOT NULL), `action` (VARCHAR(50), NOT NULL), `payload` (JSONB, NOT NULL), `reasoning` (TEXT, nullable), `created_at` (TIMESTAMPTZ, NOT NULL)

### Backend — Enums

- [ ] `backend/src/enums/` é um package com arquivos por domínio: `agents.py`, `trucks.py`, `facilities.py`, `routes.py`, `events.py`, `orders.py`. O `__init__.py` re-exporta todas as classes — imports sempre via `from src.enums import <Class>`. Define as seguintes classes `enum.Enum` (valores em snake_case como strings):
  - `AgentType`: `FACTORY="factory"`, `WAREHOUSE="warehouse"`, `STORE="store"`, `TRUCK="truck"`, `MASTER="master"`
  - `TruckType`: `PROPRIETARIO="proprietario"`, `TERCEIRO="terceiro"`
  - `TruckStatus`: `IDLE="idle"`, `EVALUATING="evaluating"`, `IN_TRANSIT="in_transit"`, `BROKEN="broken"`, `MAINTENANCE="maintenance"`
  - `FactoryStatus`: `OPERATING="operating"`, `STOPPED="stopped"`, `REDUCED_CAPACITY="reduced_capacity"`
  - `WarehouseStatus`: `OPERATING="operating"`, `RATIONING="rationing"`, `OFFLINE="offline"`
  - `StoreStatus`: `OPEN="open"`, `DEMAND_PAUSED="demand_paused"`, `OFFLINE="offline"`
  - `RouteNodeType`: `FACTORY="factory"`, `WAREHOUSE="warehouse"`, `STORE="store"`
  - `RouteStatus`: `ACTIVE="active"`, `COMPLETED="completed"`, `INTERRUPTED="interrupted"`
  - `ChaosEventSource`: `USER="user"`, `MASTER_AGENT="master_agent"`, `ENGINE="engine"`
  - `ChaosEventEntityType`: `FACTORY="factory"`, `WAREHOUSE="warehouse"`, `STORE="store"`, `TRUCK="truck"`
  - `ChaosEventStatus`: `ACTIVE="active"`, `RESOLVED="resolved"`
  - `OrderStatus`: `PENDING="pending"`, `CONFIRMED="confirmed"`, `REJECTED="rejected"`, `DELIVERED="delivered"`, `CANCELLED="cancelled"`
  - `OrderRequesterType`: `STORE="store"`, `WAREHOUSE="warehouse"`
  - `OrderTargetType`: `WAREHOUSE="warehouse"`, `FACTORY="factory"`
- [ ] Colunas dos modelos permanecem `String` — sem PostgreSQL native ENUM. Os enums são usados no código Python; o banco aceita qualquer string.

### Backend — Base e Integração

- [ ] Todos os modelos herdam de uma única `Base = declarative_base()` definida em `backend/src/database/models/__init__.py`
- [ ] `backend/src/database/models/__init__.py` importa e re-exporta todas as classes de modelo (`Material`, `Factory`, `FactoryProduct`, `FactoryPartnerWarehouse`, `Warehouse`, `WarehouseStock`, `Store`, `StoreStock`, `Truck`, `Route`, `PendingOrder`, `ChaosEvent`, `AgentDecision`)
- [ ] `backend/src/database/migrations/env.py` importa `Base` de `src.database.models` e seta `target_metadata = Base.metadata`
- [ ] FKs entre modelos usam os nomes de tabela corretos conforme `design.md §1` (ex: `FK→factories`, `FK→materials`, `FK→trucks`)

### Testes

- [ ] `backend/tests/unit/database/models/test_material.py` verifica: nome da tabela (`materials`), existência e tipo de cada coluna, default de `is_active=True`
- [ ] `backend/tests/unit/database/models/test_factory.py` verifica: tabelas `factories`, `factory_products`, `factory_partner_warehouses`; PKs compostas; default de `stock_reserved=0`; colunas de produção
- [ ] `backend/tests/unit/database/models/test_warehouse.py` verifica: tabelas `warehouses`, `warehouse_stocks`; PK composta; default de `stock_reserved=0`
- [ ] `backend/tests/unit/database/models/test_store.py` verifica: tabelas `stores`, `store_stocks`; PK composta; colunas de demanda
- [ ] `backend/tests/unit/database/models/test_truck.py` verifica: tabela `trucks`; todas as colunas FLOAT de posição; `cargo` como JSONB; `factory_id` nullable; `active_route_id` nullable
- [ ] `backend/tests/unit/database/models/test_route.py` verifica: `id` é UUID; `path` e `timestamps` são JSONB NOT NULL; `completed_at` nullable
- [ ] `backend/tests/unit/database/models/test_order.py` verifica: `id` é UUID; `status` valores válidos; `age_ticks` default=0; campos nullable corretamente
- [ ] `backend/tests/unit/database/models/test_event.py` verifica: `id` é UUID; `entity_type` e `entity_id` nullable; `tick_end` nullable
- [ ] `backend/tests/unit/database/models/test_agent_decision.py` verifica: `id` é UUID; `reasoning` nullable; todos os campos obrigatórios presentes
- [ ] `backend/tests/unit/database/models/test_enums.py` verifica: existência de cada classe enum; valores string corretos para cada membro; contagem de membros por classe (garante que nenhum valor foi omitido ou adicionado acidentalmente)
- [ ] Todos os testes passam com `pytest backend/tests/unit/database/models/` sem precisar de banco de dados real

---

## Fora do Escopo

- Criação das migrations Alembic — coberto pela feature 03
- Dados de seed (mundo padrão) — coberto pela feature 03
- Queries e métodos de acesso ao banco (repositories) — coberto pela feature 04
- Lógica de negócio em qualquer camada acima dos modelos
- PostGIS / tipos geográficos — rotas usam JSONB com coordenadas lat/lng simples, sem `geometry` do PostGIS
