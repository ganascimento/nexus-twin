# Feature 04 — Repositories

## Objetivo

Implementar a camada de acesso ao banco de dados para todas as entidades do sistema. Os repositories encapsulam todas as queries SQLAlchemy Async, expondo métodos com assinaturas explícitas que os services consomem sem tocar na `AsyncSession` diretamente. Esta feature é o único ponto de acesso ao PostgreSQL — sem ela, nenhum service, agent ou engine pode ler ou escrever estado persistente.

---

## Critérios de Aceitação

### Backend

#### `MaterialRepository` — `repositories/material.py`

- [ ] `get_all(active_only: bool) → list[Material]` retorna todos os materiais; quando `active_only=True`, filtra por `is_active = true`
- [ ] `get_by_id(id: str) → Material | None` retorna `None` quando o id não existe
- [ ] `create(data: dict) → Material` insere e retorna o registro criado
- [ ] `update(id: str, data: dict) → Material` atualiza os campos presentes em `data` e retorna o registro atualizado
- [ ] `has_linked_entities(id: str) → bool` retorna `True` se existe ao menos um registro em `factory_products`, `warehouse_stocks` ou `store_stocks` com `material_id = id`

#### `FactoryRepository` — `repositories/factory.py`

- [ ] `get_all() → list[Factory]` retorna fábricas com join em `factory_products` (sem N+1)
- [ ] `get_by_id(id: str) → Factory | None` retorna fábrica com produtos, caminhões vinculados (`trucks.factory_id`) e `factory_partner_warehouses`
- [ ] `create(data: dict) → Factory` insere `factories` + `factory_products` + `factory_partner_warehouses` em uma única transação
- [ ] `update(id: str, data: dict) → Factory` reconcilia `factory_products` e `factory_partner_warehouses` (insere novos, remove removidos, atualiza existentes)
- [ ] `delete(id: str) → None` remove `factories` e todos os registros dependentes (`factory_products`, `factory_partner_warehouses`)
- [ ] `update_product_stock(factory_id: str, material_id: str, delta: float) → None` executa `UPDATE factory_products SET stock = stock + delta WHERE factory_id = ? AND material_id = ?`
- [ ] `update_production_rate(factory_id: str, material_id: str, rate: float) → None` atualiza `production_rate_current`

#### `WarehouseRepository` — `repositories/warehouse.py`

- [ ] `get_all() → list[Warehouse]` retorna armazéns com join em `warehouse_stocks` (sem N+1)
- [ ] `get_by_id(id: str) → Warehouse | None` retorna armazém com `warehouse_stocks`
- [ ] `create(data: dict) → Warehouse` insere `warehouses` + `warehouse_stocks` em uma única transação
- [ ] `update(id: str, data: dict) → Warehouse` reconcilia `warehouse_stocks` (insere novos materiais, remove removidos, atualiza existentes)
- [ ] `delete(id: str) → None` remove `warehouses` e todos os `warehouse_stocks` associados
- [ ] `update_stock(warehouse_id: str, material_id: str, delta: float) → None` executa `UPDATE warehouse_stocks SET stock = stock + delta WHERE warehouse_id = ? AND material_id = ?`
- [ ] `get_total_stock_used(warehouse_id: str) → float` retorna a soma de `stock` de todos os produtos do armazém

#### `StoreRepository` — `repositories/store.py`

- [ ] `get_all() → list[Store]` retorna lojas com join em `store_stocks` (sem N+1)
- [ ] `get_by_id(id: str) → Store | None` retorna loja com `store_stocks`
- [ ] `create(data: dict) → Store` insere `stores` + `store_stocks` em uma única transação
- [ ] `update(id: str, data: dict) → Store` reconcilia `store_stocks`
- [ ] `delete(id: str) → None` remove `stores` e todos os `store_stocks` associados
- [ ] `update_stock(store_id: str, material_id: str, delta: float) → None` executa `UPDATE store_stocks SET stock = stock + delta WHERE store_id = ? AND material_id = ?`

#### `TruckRepository` — `repositories/truck.py`

- [ ] `get_all() → list[Truck]` retorna todos os caminhões
- [ ] `get_by_id(id: str) → Truck | None`
- [ ] `get_by_factory(factory_id: str) → list[Truck]` retorna caminhões com `factory_id = ?` (apenas proprietários)
- [ ] `create(data: dict) → Truck` insere caminhão
- [ ] `delete(id: str) → None` remove caminhão
- [ ] `update_status(id: str, status: str) → None` atualiza coluna `status`
- [ ] `try_lock_for_evaluation(truck_id: str) → bool` executa `SELECT ... FOR UPDATE SKIP LOCKED` filtrando por `id = ?` e `status = 'idle'`; se encontrar a linha, atualiza `status → 'evaluating'` via ORM e chama `flush()`; retorna `True` se bem-sucedido, `False` se a linha não existe, não era `idle` ou já estava bloqueada por outra transação
- [ ] `update_position(id: str, lat: float, lng: float) → None` atualiza `current_lat` e `current_lng`
- [ ] `update_degradation(id: str, degradation: float, breakdown_risk: float) → None` atualiza `degradation` e `breakdown_risk`
- [ ] `set_cargo(id: str, cargo: dict | None) → None` atualiza coluna `cargo` (aceita `None` para limpar)
- [ ] `set_active_route(id: str, route_id: UUID | None) → None` atualiza `active_route_id`

#### `RouteRepository` — `repositories/route.py`

- [ ] `create(data: dict) → Route` persiste rota com `path` e `timestamps` como JSONB
- [ ] `get_by_id(id: UUID) → Route | None`
- [ ] `get_active_by_truck(truck_id: str) → Route | None` retorna a rota com `status = 'active'` do caminhão, ou `None` se não houver
- [ ] `update_status(id: UUID, status: str, completed_at=None) → None` atualiza `status`; quando `status = 'completed'`, persiste `completed_at`

#### `OrderRepository` — `repositories/order.py`

- [ ] `create(data: dict) → PendingOrder` insere pedido com `age_ticks = 0`
- [ ] `get_by_id(id: UUID) → PendingOrder | None`
- [ ] `get_pending_for_target(target_id: str) → list[PendingOrder]` retorna pedidos com `target_id = ?` e `status` em `('pending', 'confirmed')`
- [ ] `get_pending_for_requester(requester_id: str) → list[PendingOrder]` retorna pedidos com `requester_id = ?` e `status` em `('pending', 'confirmed')`
- [ ] `increment_all_age_ticks() → None` executa `UPDATE pending_orders SET age_ticks = age_ticks + 1 WHERE status IN ('pending', 'confirmed')` em uma única query
- [ ] `update_status(id: UUID, status: str, **kwargs) → PendingOrder` atualiza `status` mais quaisquer campos extras passados via `kwargs` (`eta_ticks`, `rejection_reason`, `cancellation_reason`)
- [ ] `bulk_cancel_by_target(target_id: str, reason: str, skip_active_routes: bool = True) → list[UUID]` cancela em bulk pedidos `pending`/`confirmed` cujo `target_id` é a entidade; quando `skip_active_routes=True`, exclui pedidos onde o caminhão já tem `active_route_id IS NOT NULL`; retorna lista de `requester_id` afetados
- [ ] `bulk_cancel_by_requester(requester_id: str, reason: str) → None` cancela em bulk todos os pedidos `pending`/`confirmed` emitidos por `requester_id`

#### `EventRepository` — `repositories/event.py`

- [ ] `get_active() → list[ChaosEvent]` retorna eventos com `status = 'active'`
- [ ] `create(data: dict) → ChaosEvent` insere novo evento
- [ ] `resolve(id: UUID, tick_end: int) → ChaosEvent` atualiza `status = 'resolved'` e `tick_end`
- [ ] `count_active() → int` retorna a contagem de eventos com `status = 'active'`
- [ ] `get_last_resolved_autonomous_tick() → int | None` retorna o `tick_end` do evento autônomo (`source = 'master_agent'`) resolvido mais recentemente, ou `None` se não houver

#### `AgentDecisionRepository` — `repositories/agent_decision.py`

- [ ] `create(data: dict) → AgentDecision` insere decisão de um agente
- [ ] `get_recent_by_entity(entity_id: str, limit: int) → list[AgentDecision]` retorna as últimas `limit` decisões de `entity_id`, ordenadas por `created_at DESC`
- [ ] `get_all(entity_id: str | None, limit: int) → list[AgentDecision]` retorna decisões recentes; quando `entity_id` é passado, filtra por entidade; ordena por `created_at DESC`

### Testes

- [ ] Todos os testes passam com `pytest` usando uma `AsyncSession` mockada (sem banco real)
- [ ] `try_lock_for_evaluation` tem teste explícito para o caso `idle → evaluating` (retorna `True`) e o caso em que o caminhão já está em outro estado (retorna `False`)
- [ ] `bulk_cancel_by_target` com `skip_active_routes=True` não cancela pedido cujo caminhão tem `active_route_id IS NOT NULL`
- [ ] `increment_all_age_ticks` não afeta pedidos com `status = 'delivered'`, `'rejected'` ou `'cancelled'`

---

## Fora do Escopo

- ORM models (`database/models/`) — cobertos pela feature 02
- Migrations e seed (`database/migrations/`, `database/seed.py`) — cobertos pela feature 03
- Services (`services/`) — cobertos pela feature 06
- Lógica de negócio de qualquer tipo — repositories executam queries puras, sem regras de domínio
- Integração com Redis, Pub/Sub ou WebSockets — cobertos pelas features 13 e 14
- Reserva de estoque atômica via `UPDATE … WHERE stock - stock_reserved >= qty` — responsabilidade do `WarehouseService` (feature 06), não do repository
