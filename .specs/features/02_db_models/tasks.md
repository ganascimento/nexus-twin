# Tasks — Feature 02: DB Models

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — estrutura de pastas (§3), convenções (§8), regra de TDD (§9)
- `.specs/features/02_db_models/specs.md` — critérios de aceitação (todos os nomes de tabela, colunas, tipos e constraints vêm daqui)
- `.specs/design.md §1` — diagrama de tabelas e schema completo de cada tabela

Não leia specs de outras features. Esta feature não depende de nenhuma lógica de negócio além do scaffold da feature 01.

---

## Plano de Execução

**Grupo 1** roda primeiro (sozinho) — escreve todos os testes e para.
**Após aprovação do usuário**, os **Grupos 2A–2D** rodam em paralelo (sem dependências entre si).
**Grupo 3** roda por último (sozinho) — só após Grupos 2A–2D estarem concluídos.

---

### Grupo 1 — Testes (um agente) ⚠ FASE 1 — TDD

**Tarefa:** Escrever todos os testes unitários dos modelos SQLAlchemy. Não implementar nenhum modelo de produção.

1. Criar `backend/tests/__init__.py` (vazio) e `backend/tests/unit/__init__.py` (vazio) e `backend/tests/unit/database/__init__.py` (vazio) e `backend/tests/unit/database/models/__init__.py` (vazio) — se ainda não existirem

2. Criar `backend/tests/unit/database/models/test_material.py`:
   - Importa `Material` de `src.database.models`
   - `test_table_name` — verifica `Material.__tablename__ == "materials"`
   - `test_columns_exist` — verifica que o mapper tem as colunas `id`, `name`, `is_active`, `created_at`
   - `test_id_is_primary_key` — verifica que `id` é PK
   - `test_is_active_default` — instancia `Material(id="x", name="X")` e verifica `is_active is True`

3. Criar `backend/tests/unit/database/models/test_factory.py`:
   - Importa `Factory`, `FactoryProduct`, `FactoryPartnerWarehouse` de `src.database.models`
   - `test_factory_table_name` — `factories`
   - `test_factory_product_table_name` — `factory_products`
   - `test_factory_partner_warehouses_table_name` — `factory_partner_warehouses`
   - `test_factory_product_composite_pk` — verifica que `factory_id` e `material_id` são ambas PK em `FactoryProduct`
   - `test_factory_product_stock_reserved_default` — instancia e verifica `stock_reserved == 0`
   - `test_factory_partner_warehouse_composite_pk` — verifica PKs compostas
   - `test_factory_has_status_column` — verifica coluna `status` existe no mapper

4. Criar `backend/tests/unit/database/models/test_warehouse.py`:
   - Importa `Warehouse`, `WarehouseStock` de `src.database.models`
   - `test_warehouse_table_name` — `warehouses`
   - `test_warehouse_stock_table_name` — `warehouse_stocks`
   - `test_warehouse_stock_composite_pk` — verifica PKs compostas
   - `test_warehouse_stock_stock_reserved_default` — instancia e verifica `stock_reserved == 0`
   - `test_warehouse_has_region_column`

5. Criar `backend/tests/unit/database/models/test_store.py`:
   - Importa `Store`, `StoreStock` de `src.database.models`
   - `test_store_table_name` — `stores`
   - `test_store_stock_table_name` — `store_stocks`
   - `test_store_stock_composite_pk`
   - `test_store_stock_has_demand_rate_column`
   - `test_store_stock_has_reorder_point_column`

6. Criar `backend/tests/unit/database/models/test_truck.py`:
   - Importa `Truck` de `src.database.models`
   - `test_table_name` — `trucks`
   - `test_has_position_columns` — verifica `base_lat`, `base_lng`, `current_lat`, `current_lng`
   - `test_factory_id_is_nullable` — verifica que a coluna `factory_id` é nullable
   - `test_active_route_id_is_nullable` — verifica que `active_route_id` é nullable
   - `test_cargo_is_json_type` — verifica que o tipo da coluna `cargo` é JSONB ou JSON

7. Criar `backend/tests/unit/database/models/test_route.py`:
   - Importa `Route` de `src.database.models`
   - `test_table_name` — `routes`
   - `test_id_is_uuid` — verifica que o tipo da coluna `id` é UUID
   - `test_path_is_json_type`
   - `test_timestamps_is_json_type`
   - `test_completed_at_is_nullable`

8. Criar `backend/tests/unit/database/models/test_order.py`:
   - Importa `PendingOrder` de `src.database.models`
   - `test_table_name` — `pending_orders`
   - `test_id_is_uuid`
   - `test_age_ticks_default` — instancia e verifica `age_ticks == 0`
   - `test_nullable_fields` — verifica que `retry_after_tick`, `rejection_reason`, `cancellation_reason`, `eta_ticks` são nullable

9. Criar `backend/tests/unit/database/models/test_event.py`:
   - Importa `ChaosEvent` de `src.database.models`
   - `test_table_name` — `events`
   - `test_id_is_uuid`
   - `test_entity_fields_are_nullable` — verifica `entity_type` e `entity_id` nullable
   - `test_tick_end_is_nullable`

10. Criar `backend/tests/unit/database/models/test_agent_decision.py`:
    - Importa `AgentDecision` de `src.database.models`
    - `test_table_name` — `agent_decisions`
    - `test_id_is_uuid`
    - `test_reasoning_is_nullable`
    - `test_required_columns_exist` — verifica `agent_type`, `entity_id`, `tick`, `event_type`, `action`, `payload`

> ⛔ **Pare aqui. Não implemente nenhum modelo de produção. Aguarde aprovação do usuário antes de continuar para os Grupos 2A–2D.**

---

### Grupo 2A — Modelos: Material e Factory (um agente)

**Tarefa:** Implementar os modelos `Material`, `Factory`, `FactoryProduct` e `FactoryPartnerWarehouse`.

1. Em `backend/src/database/models/__init__.py`:
   - Definir `Base = declarative_base()`
   - Exportar `Base` — os outros grupos importarão daqui

2. Em `backend/src/database/models/material.py`:
   - Importar `Base` de `.`
   - Definir `Material(Base)` com `__tablename__ = "materials"`
   - Colunas conforme `design.md §1`: `id` (String(50), PK), `name` (String(100), NOT NULL), `is_active` (Boolean, NOT NULL, default=True), `created_at` (TIMESTAMPTZ, NOT NULL, server_default=`func.now()`)

3. Em `backend/src/database/models/factory.py`:
   - Importar `Base` de `.`
   - Definir `Factory(Base)` com `__tablename__ = "factories"`:
     - `id` (String(50), PK), `name` (String(100), NOT NULL), `lat` (Float, NOT NULL), `lng` (Float, NOT NULL), `status` (String(20), NOT NULL), `created_at` (TIMESTAMPTZ, NOT NULL, server_default), `updated_at` (TIMESTAMPTZ, NOT NULL, server_default, onupdate)
   - Definir `FactoryProduct(Base)` com `__tablename__ = "factory_products"`:
     - PK composta via `PrimaryKeyConstraint("factory_id", "material_id")`
     - `factory_id` (String(50), FK→factories.id, NOT NULL), `material_id` (String(50), FK→materials.id, NOT NULL)
     - `stock` (Float, NOT NULL), `stock_reserved` (Float, NOT NULL, default=0), `stock_max` (Float, NOT NULL), `production_rate_max` (Float, NOT NULL), `production_rate_current` (Float, NOT NULL)
   - Definir `FactoryPartnerWarehouse(Base)` com `__tablename__ = "factory_partner_warehouses"`:
     - PK composta via `PrimaryKeyConstraint("factory_id", "warehouse_id")`
     - `factory_id` (String(50), FK→factories.id, NOT NULL), `warehouse_id` (String(50), FK→warehouses.id, NOT NULL), `priority` (Integer, NOT NULL)

---

### Grupo 2B — Modelos: Warehouse e Store (um agente)

**Tarefa:** Implementar os modelos `Warehouse`, `WarehouseStock`, `Store` e `StoreStock`.

1. Em `backend/src/database/models/warehouse.py`:
   - Importar `Base` de `.`
   - Definir `Warehouse(Base)` com `__tablename__ = "warehouses"`:
     - `id` (String(50), PK), `name` (String(100), NOT NULL), `lat` (Float, NOT NULL), `lng` (Float, NOT NULL), `region` (String(100), NOT NULL), `capacity_total` (Float, NOT NULL), `status` (String(20), NOT NULL), `created_at`, `updated_at` (TIMESTAMPTZ, NOT NULL, server_default/onupdate)
   - Definir `WarehouseStock(Base)` com `__tablename__ = "warehouse_stocks"`:
     - PK composta via `PrimaryKeyConstraint("warehouse_id", "material_id")`
     - `warehouse_id` (String(50), FK→warehouses.id, NOT NULL), `material_id` (String(50), FK→materials.id, NOT NULL)
     - `stock` (Float, NOT NULL), `stock_reserved` (Float, NOT NULL, default=0), `min_stock` (Float, NOT NULL)

2. Em `backend/src/database/models/store.py`:
   - Importar `Base` de `.`
   - Definir `Store(Base)` com `__tablename__ = "stores"`:
     - `id` (String(50), PK), `name` (String(100), NOT NULL), `lat` (Float, NOT NULL), `lng` (Float, NOT NULL), `status` (String(20), NOT NULL), `created_at`, `updated_at` (TIMESTAMPTZ, NOT NULL, server_default/onupdate)
   - Definir `StoreStock(Base)` com `__tablename__ = "store_stocks"`:
     - PK composta via `PrimaryKeyConstraint("store_id", "material_id")`
     - `store_id` (String(50), FK→stores.id, NOT NULL), `material_id` (String(50), FK→materials.id, NOT NULL)
     - `stock` (Float, NOT NULL), `demand_rate` (Float, NOT NULL), `reorder_point` (Float, NOT NULL)

---

### Grupo 2C — Modelos: Truck e Route (um agente)

**Tarefa:** Implementar os modelos `Truck` e `Route`.

1. Em `backend/src/database/models/route.py`:
   - Importar `Base` de `.`
   - Definir `Route(Base)` com `__tablename__ = "routes"`:
     - `id` (UUID, PK, default=`uuid.uuid4`)
     - `truck_id` (String(50), FK→trucks.id, NOT NULL)
     - `origin_type` (String(20), NOT NULL), `origin_id` (String(50), NOT NULL)
     - `dest_type` (String(20), NOT NULL), `dest_id` (String(50), NOT NULL)
     - `path` (JSONB, NOT NULL), `timestamps` (JSONB, NOT NULL)
     - `eta_ticks` (Integer, NOT NULL)
     - `status` (String(20), NOT NULL)
     - `started_at` (TIMESTAMPTZ, NOT NULL), `completed_at` (TIMESTAMPTZ, nullable)

2. Em `backend/src/database/models/truck.py`:
   - Importar `Base` de `.`
   - Definir `Truck(Base)` com `__tablename__ = "trucks"`:
     - `id` (String(50), PK)
     - `truck_type` (String(20), NOT NULL)
     - `capacity_tons` (Float, NOT NULL)
     - `base_lat` (Float, NOT NULL), `base_lng` (Float, NOT NULL)
     - `current_lat` (Float, NOT NULL), `current_lng` (Float, NOT NULL)
     - `degradation` (Float, NOT NULL), `breakdown_risk` (Float, NOT NULL)
     - `status` (String(20), NOT NULL)
     - `factory_id` (String(50), FK→factories.id, nullable=True)
     - `cargo` (JSONB, nullable=True)
     - `active_route_id` (String(50), FK→routes.id, nullable=True)
     - `created_at`, `updated_at` (TIMESTAMPTZ, NOT NULL, server_default/onupdate)
   - Atenção: `Truck` tem FK→`routes.id` e `Route` tem FK→`trucks.id` — use `use_alter=True` ou `ForeignKey(..., use_alter=True)` em uma das FKs para quebrar a dependência circular de DDL

---

### Grupo 2D — Modelos: Order, Event e AgentDecision (um agente)

**Tarefa:** Implementar os modelos `PendingOrder`, `ChaosEvent` e `AgentDecision`.

1. Em `backend/src/database/models/order.py`:
   - Importar `Base` de `.`
   - Definir `PendingOrder(Base)` com `__tablename__ = "pending_orders"`:
     - `id` (UUID, PK, default=`uuid.uuid4`)
     - `requester_type` (String(20), NOT NULL), `requester_id` (String(50), NOT NULL)
     - `target_type` (String(20), NOT NULL), `target_id` (String(50), NOT NULL)
     - `material_id` (String(50), FK→materials.id, NOT NULL)
     - `quantity_tons` (Float, NOT NULL)
     - `status` (String(20), NOT NULL)
     - `age_ticks` (Integer, NOT NULL, default=0)
     - `retry_after_tick` (Integer, nullable=True)
     - `rejection_reason` (Text, nullable=True)
     - `cancellation_reason` (Text, nullable=True)
     - `eta_ticks` (Integer, nullable=True)
     - `created_at`, `updated_at` (TIMESTAMPTZ, NOT NULL, server_default/onupdate)

2. Em `backend/src/database/models/event.py`:
   - Importar `Base` de `.`
   - Definir `ChaosEvent(Base)` com `__tablename__ = "events"`:
     - `id` (UUID, PK, default=`uuid.uuid4`)
     - `event_type` (String(50), NOT NULL), `source` (String(20), NOT NULL)
     - `entity_type` (String(20), nullable=True), `entity_id` (String(50), nullable=True)
     - `payload` (JSONB, NOT NULL)
     - `status` (String(20), NOT NULL)
     - `tick_start` (Integer, NOT NULL), `tick_end` (Integer, nullable=True)
     - `created_at` (TIMESTAMPTZ, NOT NULL, server_default=`func.now()`)

3. Em `backend/src/database/models/agent_decision.py`:
   - Importar `Base` de `.`
   - Definir `AgentDecision(Base)` com `__tablename__ = "agent_decisions"`:
     - `id` (UUID, PK, default=`uuid.uuid4`)
     - `agent_type` (String(20), NOT NULL), `entity_id` (String(50), NOT NULL)
     - `tick` (Integer, NOT NULL), `event_type` (String(50), NOT NULL)
     - `action` (String(50), NOT NULL), `payload` (JSONB, NOT NULL)
     - `reasoning` (Text, nullable=True)
     - `created_at` (TIMESTAMPTZ, NOT NULL, server_default=`func.now()`)

---

### Grupo 3 — Integração e Validação (sequencial, após Grupos 2A–2D)

**Tarefa:** Amarrar todos os modelos no `__init__.py`, atualizar o `env.py` do Alembic e confirmar que todos os testes passam.

1. Atualizar `backend/src/database/models/__init__.py`:
   - Manter `Base = declarative_base()`
   - Importar e re-exportar todas as classes dos arquivos dos Grupos 2A–2D:
     ```python
     from .material import Material
     from .factory import Factory, FactoryProduct, FactoryPartnerWarehouse
     from .warehouse import Warehouse, WarehouseStock
     from .store import Store, StoreStock
     from .truck import Truck
     from .route import Route
     from .order import PendingOrder
     from .event import ChaosEvent
     from .agent_decision import AgentDecision
     ```
   - Exportar `__all__` com todos os nomes acima mais `Base`

2. Atualizar `backend/src/database/migrations/env.py`:
   - Adicionar `from src.database.models import Base`
   - Substituir `target_metadata = None` por `target_metadata = Base.metadata`

3. Rodar `pytest backend/tests/unit/database/models/ -v` e confirmar que todos os testes passam sem banco de dados real

4. Se algum teste falhar, corrigir o modelo correspondente e rodar novamente antes de marcar como concluído

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos e `pytest backend/tests/unit/database/models/` passa com zero falhas.
Atualizar `state.md`: setar o status da feature `02` para `done`.
