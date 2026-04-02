# Feature 06 — Services: Entidades

## Objetivo

Implementar a camada de serviços de negócio para as entidades do mundo: `MaterialService`, `FactoryService`, `WarehouseService`, `StoreService`, `TruckService` e `OrderService`. Esta feature entrega toda a lógica de CRUD com regras de negócio — deleção com cascata de pedidos, reserva atômica de estoque, desativação de materiais com validação de vínculo — que a API REST (feature 13) e o engine de simulação (feature 07) consomem. Sem esta camada, nenhuma entidade pode ser criada, modificada ou removida com garantias de consistência.

---

## Critérios de Aceitação

### MaterialService

- [ ] `list_materials(active_only=False)` retorna todos os materiais; com `active_only=True` filtra apenas registros com `is_active=True`
- [ ] `create_material(data)` persiste e retorna o material criado com `is_active=True` por padrão
- [ ] `update_material(id, data)` atualiza apenas o campo `name` e retorna o material atualizado; levanta `NotFoundError` se `id` não existir
- [ ] `deactivate_material(id)` levanta `ConflictError` se houver registros em `factory_products`, `warehouse_stocks` ou `store_stocks` com `material_id = id`; caso contrário seta `is_active=False` e retorna o material atualizado

### FactoryService

- [ ] `list_factories()` retorna todas as fábricas com seus `factory_products` (campos `stock`, `stock_max`, `production_rate_max`, `production_rate_current`)
- [ ] `get_factory(id)` retorna fábrica completa incluindo produtos, caminhões vinculados e armazéns parceiros; levanta `NotFoundError` se não existir
- [ ] `create_factory(data)` cria a fábrica e insere os registros correspondentes em `factory_products` e `factory_partner_warehouses`
- [ ] `update_factory(id, data)` atualiza materiais produzidos, capacidades e parceiros atomicamente
- [ ] `delete_factory(id)` cancela `pending_orders` com `target_id = id` e `status IN ('pending', 'confirmed')` que não tenham caminhão com `active_route_id IS NOT NULL`, definindo `cancellation_reason = 'target_deleted'`; pedidos com caminhão em trânsito são preservados e a entrega prossegue normalmente; publica evento `entity_removed` no canal `nexus:events`
- [ ] `adjust_stock(id, material_id, delta)` aplica o delta ao campo `stock` do produto na fábrica; levanta `ValueError` se `stock + delta < 0` ou `stock + delta > stock_max`

### WarehouseService

- [ ] `list_warehouses()` retorna todos os armazéns com seus `warehouse_stocks` (campos `stock`, `stock_reserved`, `min_stock`) por produto
- [ ] `get_warehouse(id)` retorna armazém completo; levanta `NotFoundError` se não existir
- [ ] `create_warehouse(data)` cria armazém com materiais aceitos, `min_stock` e `capacity_total`
- [ ] `update_warehouse(id, data)` atualiza materiais aceitos, capacidade total e mínimos por produto
- [ ] `delete_warehouse(id)` aplica a mesma lógica de cascata de `delete_factory`; caminhões em trânsito para o armazém completam a entrega e ficam `idle` ao chegar (responsabilidade do engine)
- [ ] `confirm_order(order_id, eta_ticks)` executa `UPDATE warehouse_stocks SET stock_reserved = stock_reserved + qty WHERE stock - stock_reserved >= qty`; retorna `None` sem atualização parcial se o estoque disponível for insuficiente; retorna o `PendingOrder` atualizado em caso de sucesso
- [ ] `reject_order(order_id, reason)` rejeita o pedido com motivo e retorna o `PendingOrder` atualizado
- [ ] `adjust_stock(id, material_id, delta)` aplica delta ao `stock`; levanta `ValueError` se `stock + delta < 0`

### StoreService

- [ ] `list_stores()` retorna todas as lojas com seus `store_stocks` (campos `stock`, `demand_rate`, `reorder_point`) por produto
- [ ] `get_store(id)` retorna loja completa; levanta `NotFoundError` se não existir
- [ ] `create_store(data)` cria loja com materiais, `demand_rate` e `reorder_point` por produto
- [ ] `update_store(id, data)` atualiza materiais, demanda e reorder points
- [ ] `delete_store(id)` chama `OrderService.cancel_orders_from(requester_id=id, reason='requester_deleted')`; caminhões em trânsito para a loja completam a entrega e ficam `idle` ao chegar; publica evento `entity_removed`
- [ ] `adjust_stock(id, material_id, delta)` aplica delta ao `stock`; levanta `ValueError` se `stock + delta < 0`
- [ ] `create_order(data)` delega para `OrderService.create_order(data)` e retorna o `PendingOrder` criado

### TruckService

- [ ] `list_trucks()` retorna todos os caminhões com `current_lat`, `current_lng`, `cargo`, `degradation` e `status`
- [ ] `get_truck(id)` retorna detalhe completo incluindo rota ativa; levanta `NotFoundError` se não existir
- [ ] `create_truck(data)` persiste caminhão com `status='idle'` e `degradation=0.0` iniciais
- [ ] `delete_truck(id)` remove o caminhão; se `status = 'in_transit'`, publica evento `truck_deleted_in_transit` com os dados de `cargo` para que o engine/agente trate a reassinalação de carga; não bloqueia a deleção
- [ ] `try_lock_for_evaluation(truck_id)` executa `UPDATE trucks SET status='evaluating' WHERE id=? AND status='idle' RETURNING id` via `TruckRepository.try_lock_for_evaluation`; retorna `True` se retornou linha, `False` se o caminhão não estava `idle`
- [ ] Os métodos `assign_route`, `complete_route`, `interrupt_route` e `schedule_maintenance` existem como stubs que levantam `NotImplementedError` — implementação na feature 07

### OrderService

- [ ] `create_order(data)` persiste pedido com `status='pending'` e `age_ticks=0`
- [ ] `increment_age_ticks(tick)` incrementa `age_ticks` de todos os pedidos com `status IN ('pending', 'confirmed')`
- [ ] `get_pending_orders_for(target_id)` retorna pedidos aguardando a entidade alvo
- [ ] `confirm_order(order_id, eta_ticks)` muda status para `confirmed` e salva `eta_ticks`; a reserva de estoque é responsabilidade do `WarehouseService.confirm_order()` antes de chamar este método
- [ ] `reject_order(order_id, reason, retry_after)` muda status para `rejected`, salva `rejection_reason` e `retry_after_tick`
- [ ] `mark_delivered(order_id)` muda status para `delivered` e libera `stock_reserved` na entidade de origem via repositório correspondente
- [ ] `cancel_orders_targeting(target_id, reason)` cancela pedidos `pending`/`confirmed` com `target_id` igual ao fornecido; exclui pedidos onde o caminhão associado tem `active_route_id IS NOT NULL`; retorna lista de `requester_id` únicos dos pedidos cancelados
- [ ] `cancel_orders_from(requester_id, reason)` cancela todos os pedidos `pending`/`confirmed` emitidos pelo requester, definindo `cancellation_reason = reason`

### Geral

- [ ] As exceções `NotFoundError` e `ConflictError` estão definidas em `backend/src/services/__init__.py`
- [ ] Nenhum service acessa o banco diretamente — toda persistência é delegada para a camada de repositories (feature 04)
- [ ] Todos os métodos públicos dos services são `async`
- [ ] A suite de testes unitários em `backend/tests/unit/services/` cobre todos os critérios acima com repositórios mockados via `AsyncMock`; `pytest backend/tests/unit/services/` passa sem erros

---

## Fora do Escopo

- `SimulationService` — feature 07 (simulation_engine)
- `WorldStateService` — feature 05 (world_state)
- `ChaosService` — feature 12 (services_chaos)
- `PhysicsService` — feature 07 (simulation_engine)
- `TriggerEvaluationService` — feature 07 (simulation_engine)
- `RouteService` e integração Valhalla — feature 07 (simulation_engine)
- Endpoints REST que expõem estes services — feature 13 (api_rest)
- Publicação real em canais Redis — feature 14 (api_websocket); nesta feature o publisher é um stub/protocolo
- Implementação de `assign_route`, `complete_route`, `interrupt_route`, `schedule_maintenance` no `TruckService` — feature 07
