# Tasks — Feature 04: Repositories

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — estrutura de pastas (§3), stack (§2), convenções (§8), regra de TDD (§9)
- `.specs/features/04_repositories/specs.md` — critérios de aceitação e assinaturas de métodos
- `.specs/design.md §1` — schema completo das tabelas (nomes de colunas, tipos, constraints)
- `.specs/design.md §7` — assinaturas e descrições exatas de cada repository

Não leia specs de outras features. Os models SQLAlchemy estão em `backend/src/database/models/` (feature 02 — presumir que existem como stubs ou implementados).

---

## Plano de Execução

**Fase 1 (Grupo 1)** — Testes: único agente escreve todos os testes. Pausa obrigatória após.

**Fase 2 (Grupos 2–4)** — Implementação em paralelo após aprovação dos testes:
- Grupo 2: repositories de entidades principais (`material`, `factory`, `warehouse`, `store`)
- Grupo 3: repositories de transporte e rotas (`truck`, `route`)
- Grupo 4: repositories de eventos e decisões (`order`, `event`, `agent_decision`)

Os Grupos 2, 3 e 4 não têm dependência entre si e podem rodar como subagentes paralelos.

---

### Grupo 1 — Testes (um agente)

**Tarefa:** Escrever todos os testes unitários dos repositories usando `AsyncSession` mockada.

**Parar após criar os testes. Não implementar código de produção. Aguardar aprovação do usuário.**

1. Criar `backend/tests/unit/repositories/__init__.py` (vazio)

2. Criar `backend/tests/unit/repositories/test_material_repository.py`:
   - `test_get_all_returns_all_materials` — mock retorna lista de 2 materials; assert len == 2
   - `test_get_all_active_only_filters` — mock retorna apenas `is_active=True`; assert filtra corretamente
   - `test_get_by_id_returns_none_when_not_found` — mock retorna `None`; assert resultado é `None`
   - `test_create_inserts_and_returns` — mock da session; assert `session.add` chamado e resultado retornado
   - `test_has_linked_entities_returns_true` — mock de query que conta registros > 0; assert `True`
   - `test_has_linked_entities_returns_false` — mock de query que conta 0; assert `False`

3. Criar `backend/tests/unit/repositories/test_factory_repository.py`:
   - `test_get_all_eager_loads_products` — assert que o resultado inclui `products`; sem N+1 (query única)
   - `test_get_by_id_includes_trucks_and_partners` — assert `trucks` e `partner_warehouses` no resultado
   - `test_create_inserts_factory_products_and_partners_in_transaction` — assert que `session.add` é chamado para `Factory`, `FactoryProduct` e `FactoryPartnerWarehouse`
   - `test_update_product_stock_applies_delta` — assert query com `stock = stock + delta`
   - `test_update_production_rate` — assert atualização de `production_rate_current`

4. Criar `backend/tests/unit/repositories/test_warehouse_repository.py`:
   - `test_get_all_eager_loads_stocks` — sem N+1
   - `test_create_inserts_warehouse_and_stocks` — assert transação única
   - `test_update_stock_applies_delta` — assert `stock = stock + delta`
   - `test_get_total_stock_used_sums_all_products` — mock de 2 stocks com valores 10.0 e 20.0; assert retorna 30.0

5. Criar `backend/tests/unit/repositories/test_store_repository.py`:
   - `test_get_all_eager_loads_stocks`
   - `test_create_inserts_store_and_stocks`
   - `test_update_stock_applies_delta`

6. Criar `backend/tests/unit/repositories/test_truck_repository.py`:
   - `test_get_by_factory_filters_by_factory_id`
   - `test_try_lock_for_evaluation_returns_true_when_idle` — mock: `rowcount = 1`; assert retorna `True`
   - `test_try_lock_for_evaluation_returns_false_when_not_idle` — mock: `rowcount = 0`; assert retorna `False`
   - `test_set_cargo_accepts_none` — assert query com `cargo = None`
   - `test_update_degradation_updates_both_fields` — assert `degradation` e `breakdown_risk` atualizados

7. Criar `backend/tests/unit/repositories/test_route_repository.py`:
   - `test_get_active_by_truck_returns_none_when_no_active_route` — mock de query sem resultado; assert `None`
   - `test_update_status_sets_completed_at_when_completed` — status `'completed'`, assert `completed_at` preenchido
   - `test_update_status_does_not_set_completed_at_when_interrupted` — status `'interrupted'`, assert `completed_at = None`

8. Criar `backend/tests/unit/repositories/test_order_repository.py`:
   - `test_get_pending_for_target_only_returns_pending_confirmed` — mock com pedidos em statuses variados; assert apenas `pending` e `confirmed`
   - `test_increment_all_age_ticks_bulk_update` — assert query `UPDATE … WHERE status IN ('pending', 'confirmed')`; assert pedidos `delivered` não afetados
   - `test_bulk_cancel_by_target_skips_active_routes` — mock com 1 pedido com `active_route_id IS NOT NULL`; assert esse pedido não é cancelado; assert retorna IDs dos requesters afetados
   - `test_bulk_cancel_by_target_without_skip` — com `skip_active_routes=False`, cancela todos os pedidos incluindo os com rota ativa
   - `test_bulk_cancel_by_requester_cancels_all_from_requester`

9. Criar `backend/tests/unit/repositories/test_event_repository.py`:
   - `test_get_active_filters_by_status`
   - `test_count_active_returns_integer`
   - `test_get_last_resolved_autonomous_tick_returns_none_when_none_exist`
   - `test_resolve_updates_status_and_tick_end`

10. Criar `backend/tests/unit/repositories/test_agent_decision_repository.py`:
    - `test_get_recent_by_entity_orders_by_created_at_desc`
    - `test_get_all_filters_by_entity_id_when_provided`
    - `test_get_all_returns_all_when_entity_id_is_none`

---

### Grupo 2 — Repositories de Entidades (um agente)

**Tarefa:** Implementar `MaterialRepository`, `FactoryRepository`, `WarehouseRepository` e `StoreRepository`.

**Depende:** aprovação dos testes do Grupo 1.

1. Implementar `backend/src/repositories/material.py`:
   - Classe `MaterialRepository` recebe `AsyncSession` no `__init__`
   - `get_all(active_only: bool)` — `select(Material)`, adiciona `where(Material.is_active == True)` se `active_only`
   - `get_by_id(id: str)` — `select(Material).where(Material.id == id)`, retorna `None` se não encontrado
   - `create(data: dict)` — instancia `Material(**data)`, `session.add`, `await session.flush()`, `await session.refresh(obj)`, retorna obj
   - `update(id: str, data: dict)` — busca por id, atualiza campos, flush, refresh, retorna obj
   - `has_linked_entities(id: str)` — query `EXISTS` (ou count > 0) em `factory_products`, `warehouse_stocks`, `store_stocks` com `material_id = id`

2. Implementar `backend/src/repositories/factory.py`:
   - Classe `FactoryRepository` recebe `AsyncSession` no `__init__`
   - `get_all()` — `selectinload(Factory.products)` para evitar N+1
   - `get_by_id(id: str)` — `selectinload` de `products`, `trucks` e `partner_warehouses`
   - `create(data: dict)` — insere `Factory` + `FactoryProduct[]` + `FactoryPartnerWarehouse[]` em uma única transação; extrair `products` e `partner_warehouses` de `data` antes de criar a `Factory`
   - `update(id: str, data: dict)` — reconcilia products/partners: apaga os removidos, insere os novos, atualiza os existentes
   - `delete(id: str)` — remove `factory_partner_warehouses`, `factory_products`, então `factories` (na ordem correta para FK constraints)
   - `update_product_stock(factory_id, material_id, delta)` — `UPDATE factory_products SET stock = stock + :delta WHERE factory_id = :fid AND material_id = :mid`
   - `update_production_rate(factory_id, material_id, rate)` — `UPDATE factory_products SET production_rate_current = :rate WHERE factory_id = :fid AND material_id = :mid`

3. Implementar `backend/src/repositories/warehouse.py`:
   - Classe `WarehouseRepository` recebe `AsyncSession` no `__init__`
   - `get_all()` — `selectinload(Warehouse.stocks)`
   - `get_by_id(id: str)` — `selectinload(Warehouse.stocks)`
   - `create(data: dict)` — insere `Warehouse` + `WarehouseStock[]` em transação
   - `update(id: str, data: dict)` — reconcilia `warehouse_stocks` (mantém `stock` atual dos existentes, insere novos com `stock=0`, remove removidos)
   - `delete(id: str)` — remove `warehouse_stocks`, depois `warehouses`
   - `update_stock(warehouse_id, material_id, delta)` — `UPDATE warehouse_stocks SET stock = stock + :delta WHERE warehouse_id = :wid AND material_id = :mid`
   - `get_total_stock_used(warehouse_id: str)` — `SELECT COALESCE(SUM(stock), 0) FROM warehouse_stocks WHERE warehouse_id = :wid`

4. Implementar `backend/src/repositories/store.py`:
   - Classe `StoreRepository` recebe `AsyncSession` no `__init__`
   - `get_all()` — `selectinload(Store.stocks)`
   - `get_by_id(id: str)` — `selectinload(Store.stocks)`
   - `create(data: dict)` — insere `Store` + `StoreStock[]` em transação
   - `update(id: str, data: dict)` — reconcilia `store_stocks`
   - `delete(id: str)` — remove `store_stocks`, depois `stores`
   - `update_stock(store_id, material_id, delta)` — `UPDATE store_stocks SET stock = stock + :delta WHERE store_id = :sid AND material_id = :mid`

---

### Grupo 3 — Repositories de Transporte (um agente)

**Tarefa:** Implementar `TruckRepository` e `RouteRepository`.

**Depende:** aprovação dos testes do Grupo 1.

1. Implementar `backend/src/repositories/truck.py`:
   - Classe `TruckRepository` recebe `AsyncSession` no `__init__`
   - `get_all()` — `select(Truck)`
   - `get_by_id(id: str)` — retorna `None` se não encontrado
   - `get_by_factory(factory_id: str)` — `where(Truck.factory_id == factory_id)`
   - `create(data: dict)` — insere e retorna `Truck`
   - `delete(id: str)` — remove caminhão
   - `update_status(id: str, status: str)` — `UPDATE trucks SET status = :status WHERE id = :id`
   - `try_lock_for_evaluation(truck_id: str) → bool` — execute `UPDATE trucks SET status = 'evaluating' WHERE id = :id AND status = 'idle'`; verificar `result.rowcount == 1`; **não usar select antes do update** — a atomicidade do UPDATE garante sem race condition
   - `update_position(id, lat, lng)` — atualiza `current_lat`, `current_lng`
   - `update_degradation(id, degradation, breakdown_risk)` — atualiza ambos os campos
   - `set_cargo(id, cargo: dict | None)` — atualiza coluna `cargo` (serializa `dict` ou persiste `None`)
   - `set_active_route(id, route_id: UUID | None)` — atualiza `active_route_id`

2. Implementar `backend/src/repositories/route.py`:
   - Classe `RouteRepository` recebe `AsyncSession` no `__init__`
   - `create(data: dict) → Route` — insere rota; `path` e `timestamps` são JSONB — passar como `dict`/`list` (SQLAlchemy serializa automaticamente)
   - `get_by_id(id: UUID) → Route | None`
   - `get_active_by_truck(truck_id: str) → Route | None` — `where(Route.truck_id == truck_id, Route.status == 'active')`; retorna `None` se não encontrar
   - `update_status(id: UUID, status: str, completed_at=None) → None` — atualiza `status`; se `completed_at` fornecido, persiste também

---

### Grupo 4 — Repositories de Eventos e Decisões (um agente)

**Tarefa:** Implementar `OrderRepository`, `EventRepository` e `AgentDecisionRepository`.

**Depende:** aprovação dos testes do Grupo 1.

1. Implementar `backend/src/repositories/order.py`:
   - Classe `OrderRepository` recebe `AsyncSession` no `__init__`
   - `create(data: dict) → PendingOrder` — insere com `age_ticks = 0` (forçar no dict antes de inserir se não presente)
   - `get_by_id(id: UUID) → PendingOrder | None`
   - `get_pending_for_target(target_id: str)` — `where(PendingOrder.target_id == target_id, PendingOrder.status.in_(['pending', 'confirmed']))`
   - `get_pending_for_requester(requester_id: str)` — `where(PendingOrder.requester_id == requester_id, PendingOrder.status.in_(['pending', 'confirmed']))`
   - `increment_all_age_ticks() → None` — `UPDATE pending_orders SET age_ticks = age_ticks + 1 WHERE status IN ('pending', 'confirmed')` — query única
   - `update_status(id: UUID, status: str, **kwargs) → PendingOrder` — atualiza `status` + campos extras de `kwargs` usando `update(PendingOrder).where(...).values(status=status, **kwargs)`
   - `bulk_cancel_by_target(target_id, reason, skip_active_routes=True) → list[UUID]`:
     - Seleciona pedidos `pending`/`confirmed` com `target_id = ?`
     - Se `skip_active_routes=True`, exclui aqueles cujo truck tem `active_route_id IS NOT NULL` (join em `trucks` via subquery ou join explícito)
     - Para os selecionados: `UPDATE pending_orders SET status = 'cancelled', cancellation_reason = :reason WHERE id IN (:ids)`
     - Retorna lista de `requester_id` únicos dos pedidos cancelados
   - `bulk_cancel_by_requester(requester_id, reason) → None` — `UPDATE pending_orders SET status = 'cancelled', cancellation_reason = :reason WHERE requester_id = :rid AND status IN ('pending', 'confirmed')`

2. Implementar `backend/src/repositories/event.py`:
   - Classe `EventRepository` recebe `AsyncSession` no `__init__`
   - `get_active() → list[ChaosEvent]` — `where(ChaosEvent.status == 'active')`
   - `create(data: dict) → ChaosEvent` — insere e retorna
   - `resolve(id: UUID, tick_end: int) → ChaosEvent` — atualiza `status = 'resolved'`, `tick_end = tick_end`; retorna o registro atualizado
   - `count_active() → int` — `SELECT COUNT(*) FROM events WHERE status = 'active'`
   - `get_last_resolved_autonomous_tick() → int | None` — `SELECT tick_end FROM events WHERE source = 'master_agent' AND status = 'resolved' ORDER BY tick_end DESC LIMIT 1`; retorna `None` se não encontrar

3. Implementar `backend/src/repositories/agent_decision.py`:
   - Classe `AgentDecisionRepository` recebe `AsyncSession` no `__init__`
   - `create(data: dict) → AgentDecision` — insere e retorna
   - `get_recent_by_entity(entity_id: str, limit: int) → list[AgentDecision]` — `where(AgentDecision.entity_id == entity_id).order_by(AgentDecision.created_at.desc()).limit(limit)`
   - `get_all(entity_id: str | None, limit: int) → list[AgentDecision]` — se `entity_id` passado, adiciona `where(AgentDecision.entity_id == entity_id)`; sempre `order_by(created_at DESC).limit(limit)`

4. Atualizar `backend/src/repositories/__init__.py` — exportar todas as classes de repository

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes passam com `pytest backend/tests/unit/repositories/`.
Atualizar `state.md`: setar o status da feature `04` para `done`.
