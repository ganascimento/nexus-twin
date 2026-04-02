# Tasks — Feature 06: Services Entities

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — convenções (§8), regras de TDD (§9), estrutura de pastas (§3)
- `.specs/features/06_services_entities/specs.md` — critérios de aceitação
- `.specs/design.md §6` — contrato completo de cada service (métodos, assinaturas, regras de negócio)
- `.specs/design.md §1` — schemas das tabelas (`factory_products`, `warehouse_stocks`, `store_stocks`, `pending_orders`, `trucks`) — campos, constraints, valores de status

Não leia specs de outras features. Esta feature não implementa repositories, ORM models, endpoints REST, nem lógica de simulação ou agentes.

---

## Plano de Execução

O Grupo 1 é obrigatório e sequencial: escreve todos os testes antes de qualquer implementação. Após aprovação do usuário, os Grupos 2, 3 e 4 rodam em paralelo (sem dependências entre si na fase de implementação).

---

### Grupo 1 — Testes (um agente)

**Tarefa:** Escrever todos os testes unitários para os 6 services desta feature com repositórios mockados.

**PARE após criar os testes. Não implemente código de produção. Aguarde aprovação do usuário.**

1. Criar `backend/tests/unit/services/__init__.py` (arquivo vazio)

2. Criar `backend/tests/unit/services/test_material_service.py`:
   - Setup: `AsyncMock` para `MaterialRepository`
   - `test_list_materials_returns_all` — verifica que `repo.list_all()` é chamado e resultado retornado
   - `test_list_materials_active_only_filters` — verifica que `repo.list_active()` é chamado com `active_only=True`
   - `test_create_material_delegates_to_repo`
   - `test_update_material_raises_not_found_when_repo_returns_none`
   - `test_update_material_returns_updated_material`
   - `test_deactivate_material_raises_conflict_if_referenced_by_factory` — mock `repo.has_active_references()` retornando `True`
   - `test_deactivate_material_raises_conflict_if_referenced_by_warehouse`
   - `test_deactivate_material_raises_conflict_if_referenced_by_store`
   - `test_deactivate_material_sets_is_active_false_when_no_references` — mock `repo.has_active_references()` retornando `False`

3. Criar `backend/tests/unit/services/test_factory_service.py`:
   - Setup: `AsyncMock` para `FactoryRepository`, `OrderRepository`; stub para `Publisher`
   - `test_list_factories_returns_all_with_products`
   - `test_get_factory_raises_not_found`
   - `test_get_factory_returns_complete_detail`
   - `test_create_factory_persists_with_products_and_partners`
   - `test_update_factory_updates_materials_and_partners`
   - `test_delete_factory_cancels_pending_orders_without_active_route` — dois pedidos mockados: um com `active_route_id=None` (deve ser cancelado) e um com `active_route_id='route-1'` (deve ser preservado)
   - `test_delete_factory_preserves_orders_with_active_truck_route`
   - `test_delete_factory_publishes_entity_removed_event` — verificar que o publisher é chamado com `event_type='entity_removed'`
   - `test_adjust_stock_raises_value_error_if_negative_result`
   - `test_adjust_stock_raises_value_error_if_exceeds_stock_max`
   - `test_adjust_stock_applies_valid_delta`

4. Criar `backend/tests/unit/services/test_warehouse_service.py`:
   - Setup: `AsyncMock` para `WarehouseRepository`, `OrderRepository`; stub para `Publisher`
   - `test_list_warehouses_returns_all_with_stocks`
   - `test_get_warehouse_raises_not_found`
   - `test_create_warehouse_with_materials_and_minimums`
   - `test_update_warehouse_updates_capacity_and_minimums`
   - `test_delete_warehouse_cancels_orders_without_active_route`
   - `test_delete_warehouse_preserves_orders_with_active_truck_route`
   - `test_confirm_order_calls_atomic_reserve_and_returns_updated_order` — mock `repo.atomic_reserve_stock()` retornando `True`
   - `test_confirm_order_returns_none_if_insufficient_stock` — mock `repo.atomic_reserve_stock()` retornando `False`
   - `test_reject_order_sets_reason_and_returns_order`
   - `test_adjust_stock_raises_value_error_if_negative_result`

5. Criar `backend/tests/unit/services/test_store_service.py`:
   - Setup: `AsyncMock` para `StoreRepository`; `AsyncMock` para `OrderService`; stub para `Publisher`
   - `test_list_stores_returns_all_with_stocks`
   - `test_get_store_raises_not_found`
   - `test_create_store_with_materials_demand_and_reorder`
   - `test_update_store_updates_demand_and_reorder`
   - `test_delete_store_calls_cancel_orders_from_with_correct_args` — verifica que `order_service.cancel_orders_from(requester_id=id, reason='requester_deleted')` é chamado
   - `test_delete_store_publishes_entity_removed_event`
   - `test_adjust_stock_raises_value_error_if_negative_result`
   - `test_create_order_delegates_to_order_service`

6. Criar `backend/tests/unit/services/test_truck_service.py`:
   - Setup: `AsyncMock` para `TruckRepository`; stub para `Publisher`
   - `test_list_trucks_returns_all_with_position_and_cargo`
   - `test_get_truck_raises_not_found`
   - `test_create_truck_sets_status_idle_and_degradation_zero`
   - `test_delete_truck_idle_removes_without_event`
   - `test_delete_truck_in_transit_publishes_truck_deleted_in_transit_with_cargo`
   - `test_try_lock_for_evaluation_returns_true_when_repo_succeeds` — mock `repo.try_lock_for_evaluation()` retornando o truck atualizado
   - `test_try_lock_for_evaluation_returns_false_when_repo_returns_none` — mock retornando `None`
   - `test_assign_route_raises_not_implemented`
   - `test_complete_route_raises_not_implemented`
   - `test_interrupt_route_raises_not_implemented`
   - `test_schedule_maintenance_raises_not_implemented`

7. Criar `backend/tests/unit/services/test_order_service.py`:
   - Setup: `AsyncMock` para `OrderRepository`, `WarehouseRepository`, `FactoryRepository`
   - `test_create_order_sets_pending_and_age_zero`
   - `test_increment_age_ticks_calls_repo_with_correct_statuses`
   - `test_get_pending_orders_for_target_delegates_to_repo`
   - `test_confirm_order_sets_confirmed_and_eta`
   - `test_reject_order_sets_reason_and_backoff`
   - `test_mark_delivered_releases_stock_reserved_on_warehouse` — `requester_type='warehouse'`; verifica que `warehouse_repo.release_stock_reserved()` é chamado
   - `test_mark_delivered_releases_stock_reserved_on_factory` — `requester_type='factory'`; verifica que `factory_repo.release_stock_reserved()` é chamado
   - `test_cancel_orders_targeting_skips_orders_with_active_route` — pedido com `active_route_id IS NOT NULL` não aparece na lista retornada nem no cancel
   - `test_cancel_orders_targeting_cancels_pending_and_confirmed`
   - `test_cancel_orders_targeting_returns_unique_requester_ids`
   - `test_cancel_orders_from_cancels_all_requester_pending_confirmed`

---

### Grupo 2 — MaterialService + OrderService (um agente, paralelo após Grupo 1)

**Tarefa:** Implementar `MaterialService` e `OrderService` com base nos testes aprovados.

1. Editar `backend/src/services/__init__.py`:
   - Definir `class NotFoundError(Exception): pass`
   - Definir `class ConflictError(Exception): pass`
   - Definir o protocolo `Publisher` como `typing.Protocol` com método `async def publish_event(self, event_type: str, payload: dict) -> None`

2. Criar `backend/src/services/material.py`:
   - Classe `MaterialService` com `__init__(self, repo: MaterialRepository)`
   - `list_materials(active_only: bool = False)`: chama `repo.list_active()` se `active_only` else `repo.list_all()`
   - `create_material(data: MaterialCreate) -> Material`: delega para `repo.create(data)`
   - `update_material(id: str, data: MaterialUpdate) -> Material`: chama `repo.get(id)`; levanta `NotFoundError` se `None`; delega para `repo.update(id, data)`
   - `deactivate_material(id: str) -> Material`: chama `repo.has_active_references(id)`; levanta `ConflictError` se `True`; chama `repo.deactivate(id)`

3. Criar `backend/src/services/order.py`:
   - Classe `OrderService` com `__init__(self, repo: OrderRepository, warehouse_repo: WarehouseRepository, factory_repo: FactoryRepository)`
   - `create_order(data: PendingOrderCreate) -> PendingOrder`: delega para `repo.create(data)` com `status='pending'`, `age_ticks=0`
   - `increment_age_ticks(tick: int) -> None`: chama `repo.increment_age_ticks()` que atualiza pedidos com `status IN ('pending', 'confirmed')`
   - `get_pending_orders_for(target_id: str) -> list[PendingOrder]`: delega para `repo.get_by_target(target_id)`
   - `confirm_order(order_id: UUID, eta_ticks: int) -> PendingOrder`: chama `repo.update_status(order_id, status='confirmed', eta_ticks=eta_ticks)`
   - `reject_order(order_id: UUID, reason: str, retry_after: int) -> PendingOrder`: chama `repo.update_status(order_id, status='rejected', rejection_reason=reason, retry_after_tick=retry_after)`
   - `mark_delivered(order_id: UUID) -> PendingOrder`: busca pedido via `repo.get(order_id)`; chama `warehouse_repo.release_stock_reserved(order.target_id, order.material_id, order.quantity_tons)` se `order.target_type == 'warehouse'`, senão `factory_repo.release_stock_reserved(...)`; chama `repo.update_status(order_id, status='delivered')`
   - `cancel_orders_targeting(target_id: str, reason: str) -> list[str]`: busca pedidos via `repo.get_cancellable_by_target(target_id)` (status `pending`/`confirmed`, sem rota ativa); chama `repo.bulk_cancel(ids, reason)`; retorna lista de `requester_id` únicos
   - `cancel_orders_from(requester_id: str, reason: str) -> list[PendingOrder]`: chama `repo.get_cancellable_by_requester(requester_id)` e `repo.bulk_cancel(ids, reason)`

---

### Grupo 3 — FactoryService + WarehouseService (um agente, paralelo após Grupo 1)

**Tarefa:** Implementar `FactoryService` e `WarehouseService` com base nos testes aprovados.

1. Criar `backend/src/services/factory.py`:
   - Classe `FactoryService` com `__init__(self, repo: FactoryRepository, order_repo: OrderRepository, publisher: Publisher)`
   - `list_factories() -> list[Factory]`: chama `repo.list_all_with_products()`
   - `get_factory(id: str) -> Factory`: chama `repo.get_with_detail(id)`; levanta `NotFoundError` se `None`
   - `create_factory(data: FactoryCreate) -> Factory`: chama `repo.create_with_products(data)` que insere fábrica + `factory_products` + `factory_partner_warehouses` atomicamente
   - `update_factory(id: str, data: FactoryUpdate) -> Factory`: chama `repo.update_with_products(id, data)`; levanta `NotFoundError` se fábrica não existir
   - `delete_factory(id: str) -> None`:
     1. Busca pedidos via `order_repo.get_cancellable_by_target(id)` — retorna apenas pedidos com `status IN ('pending', 'confirmed')` e `active_route_id IS NULL` no caminhão associado
     2. Se houver pedidos, chama `order_repo.bulk_cancel(ids, cancellation_reason='target_deleted')`
     3. Chama `repo.delete(id)`
     4. Chama `await publisher.publish_event('entity_removed', {'entity_type': 'factory', 'entity_id': id})`
   - `adjust_stock(id: str, material_id: str, delta: float) -> None`:
     - Busca produto via `repo.get_product(id, material_id)`; levanta `NotFoundError` se não encontrado
     - Calcula novo estoque: `new_stock = product.stock + delta`
     - Levanta `ValueError(f"stock cannot be negative: {new_stock}")` se `new_stock < 0`
     - Levanta `ValueError(f"stock exceeds stock_max: {new_stock} > {product.stock_max}")` se `new_stock > product.stock_max`
     - Chama `repo.update_stock(id, material_id, new_stock)`

2. Criar `backend/src/services/warehouse.py`:
   - Classe `WarehouseService` com `__init__(self, repo: WarehouseRepository, order_repo: OrderRepository, publisher: Publisher)`
   - `list_warehouses() -> list[Warehouse]`: chama `repo.list_all_with_stocks()`
   - `get_warehouse(id: str) -> Warehouse`: chama `repo.get_with_stocks(id)`; levanta `NotFoundError` se `None`
   - `create_warehouse(data: WarehouseCreate) -> Warehouse`: chama `repo.create_with_stocks(data)` que insere armazém + `warehouse_stocks` atomicamente
   - `update_warehouse(id: str, data: WarehouseUpdate) -> Warehouse`: chama `repo.update_with_stocks(id, data)`; levanta `NotFoundError` se armazém não existir
   - `delete_warehouse(id: str) -> None`: mesma lógica de cascata de `delete_factory` — cancela pedidos `pending`/`confirmed` sem rota ativa, remove armazém, publica `entity_removed`
   - `confirm_order(order_id: UUID, eta_ticks: int) -> PendingOrder | None`:
     1. Busca pedido via `order_repo.get(order_id)`; levanta `NotFoundError` se não existir
     2. Chama `repo.atomic_reserve_stock(warehouse_id=order.target_id, material_id=order.material_id, quantity=order.quantity_tons)` — executa `UPDATE warehouse_stocks SET stock_reserved = stock_reserved + quantity WHERE warehouse_id=? AND material_id=? AND stock - stock_reserved >= quantity RETURNING *`
     3. Se retornou `None` (sem linhas afetadas): retorna `None` sem alterar o pedido
     4. Se reserva ok: chama `order_repo.update_status(order_id, status='confirmed', eta_ticks=eta_ticks)` e retorna o pedido atualizado
   - `reject_order(order_id: UUID, reason: str) -> PendingOrder`: chama `order_repo.update_status(order_id, status='rejected', rejection_reason=reason)` e retorna o pedido
   - `adjust_stock(id: str, material_id: str, delta: float) -> None`:
     - Busca estoque via `repo.get_stock(id, material_id)`; levanta `NotFoundError` se não encontrado
     - Calcula `new_stock = stock.stock + delta`; levanta `ValueError` se `new_stock < 0`
     - Chama `repo.update_stock(id, material_id, new_stock)`

---

### Grupo 4 — StoreService + TruckService (um agente, paralelo após Grupo 1)

**Tarefa:** Implementar `StoreService` e `TruckService` com base nos testes aprovados.

1. Criar `backend/src/services/store.py`:
   - Classe `StoreService` com `__init__(self, repo: StoreRepository, order_service: OrderService, publisher: Publisher)`
   - `list_stores() -> list[Store]`: chama `repo.list_all_with_stocks()`
   - `get_store(id: str) -> Store`: chama `repo.get_with_stocks(id)`; levanta `NotFoundError` se `None`
   - `create_store(data: StoreCreate) -> Store`: chama `repo.create_with_stocks(data)` que insere loja + `store_stocks` atomicamente
   - `update_store(id: str, data: StoreUpdate) -> Store`: chama `repo.update_with_stocks(id, data)`; levanta `NotFoundError` se loja não existir
   - `delete_store(id: str) -> None`:
     1. Chama `await order_service.cancel_orders_from(requester_id=id, reason='requester_deleted')`
     2. Chama `repo.delete(id)`
     3. Chama `await publisher.publish_event('entity_removed', {'entity_type': 'store', 'entity_id': id})`
   - `adjust_stock(id: str, material_id: str, delta: float) -> None`:
     - Busca estoque via `repo.get_stock(id, material_id)`; levanta `NotFoundError` se não encontrado
     - Calcula `new_stock = stock.stock + delta`; levanta `ValueError` se `new_stock < 0`
     - Chama `repo.update_stock(id, material_id, new_stock)`
   - `create_order(data: PendingOrderCreate) -> PendingOrder`: delega diretamente para `await order_service.create_order(data)`

2. Criar `backend/src/services/truck.py`:
   - Classe `TruckService` com `__init__(self, repo: TruckRepository, publisher: Publisher)`
   - `list_trucks() -> list[Truck]`: chama `repo.list_all()`
   - `get_truck(id: str) -> Truck`: chama `repo.get_with_route(id)`; levanta `NotFoundError` se `None`
   - `create_truck(data: TruckCreate) -> Truck`: chama `repo.create(data)` garantindo `status='idle'` e `degradation=0.0` nos dados persitidos
   - `delete_truck(id: str) -> None`:
     1. Busca caminhão via `repo.get(id)`; levanta `NotFoundError` se não existir
     2. Se `truck.status == 'in_transit'`: chama `await publisher.publish_event('truck_deleted_in_transit', {'truck_id': id, 'cargo': truck.cargo})`
     3. Chama `repo.delete(id)`
   - `try_lock_for_evaluation(truck_id: str) -> bool`:
     - Chama `repo.try_lock_for_evaluation(truck_id)` — executa `UPDATE trucks SET status='evaluating' WHERE id=? AND status='idle' RETURNING id`
     - Retorna `True` se retornou linha (caminhão estava `idle` e foi bloqueado), `False` caso contrário
   - Stubs que levantam `NotImplementedError` — implementação na feature 07:
     - `async def assign_route(self, truck_id: str, route: RouteCreate) -> Route`
     - `async def complete_route(self, truck_id: str) -> None`
     - `async def interrupt_route(self, truck_id: str, reason: str) -> None`
     - `async def schedule_maintenance(self, truck_id: str) -> None`

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
`pytest backend/tests/unit/services/` passa sem erros.
Atualizar `state.md`: setar o status da feature `06` para `done`.
