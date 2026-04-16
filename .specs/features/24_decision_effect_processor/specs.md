# Feature 24 — Decision Effect Processor

## Objetivo

Implementa o **elo que falta** entre as decisões dos agentes e o estado do mundo. Hoje, quando um agente decide `confirm_order` ou `order_replenishment`, a decisão é gravada na tabela `agent_decisions` e publicada no Redis — mas **nenhum efeito colateral acontece no mundo**. PendingOrders nunca mudam de status, novas ordens nunca são criadas, caminhões nunca são despachados.

Sem esta feature, o sistema de agentes é uma cadeia aberta: a loja pede reposição, o pedido fica pendente para sempre, o armazém processa o mesmo pedido infinitamente a cada tick, e o caminhão nunca sai.

### Problema Concreto

1. **Ordens duplicadas:** StoreAgent emite `order_replenishment` a cada tick (estoque continua baixo porque nada chega). Não há deduplicação — uma nova decisão é gravada a cada vez, mas nenhum PendingOrder é criado.
2. **Ordens fantasma:** WarehouseAgent recebe `pending_orders` no `WorldStateSlice`, mas como nenhum agente muda o status para `confirmed`/`rejected`, o mesmo pedido é re-processado a cada tick por cada armazém que o vê.
3. **Cadeia quebrada:** A loja pede ao armazém, mas o armazém nunca pede à fábrica (nenhum PendingOrder novo é criado). A fábrica nunca despacha estoque. O caminhão nunca é acionado.
4. **Manutenção ignorada:** TruckAgent decide `request_maintenance`, mas `TruckService.schedule_maintenance()` nunca é chamado.

### Solução

Criar um `DecisionEffectProcessor` — um service chamado pelo nó `act` do grafo LangGraph **após persistir a decisão**. Ele mapeia cada `(entity_type, action)` para a chamada de service correspondente, aplicando os efeitos colaterais no mundo dentro da mesma transação.

---

## Critérios de Aceitacao

### Backend — `DecisionEffectProcessor`

- [ ] `backend/src/services/decision_effect_processor.py` exporta `DecisionEffectProcessor`
- [ ] Construtor recebe as dependências necessárias: `db_session`, `publisher`, e uma factory/registry de services (ou os services diretamente)
- [ ] Método principal `async process(entity_type: str, entity_id: str, action: str, payload: dict, current_tick: int) -> None` que roteia para o handler correto
- [ ] Decisões com `action: "hold"` são no-op — nenhum efeito colateral
- [ ] Se o handler falha (ex: estoque insuficiente), o erro é logado mas **não impede** a persistência da decisão (a decisão é registrada, o efeito falhou)

### Backend — Handlers por Ação

#### StoreAgent decisions

- [ ] `order_replenishment` → cria um `PendingOrder` no banco com:
  - `requester_type = "store"`, `requester_id = entity_id`
  - `target_type = "warehouse"`, `target_id = payload["from_warehouse_id"]`
  - `material_id = payload["material_id"]`
  - `quantity_tons = payload["quantity_tons"]`
  - `status = "pending"`
- [ ] Antes de criar, verifica se já existe um PendingOrder ativo (status `pending` ou `confirmed`) do mesmo `requester_id` para o mesmo `material_id` → se sim, **skip** (deduplicação, resolve o problema de ordens duplicadas)

#### WarehouseAgent decisions

- [ ] `confirm_order` → chama `WarehouseService.confirm_order(order_id, eta_ticks)` que:
  - Reserva estoque atomicamente (`atomic_reserve_stock`)
  - Atualiza PendingOrder status para `confirmed`
  - **Despacha caminhão para entrega warehouse→store:** busca caminhão terceiro `idle` mais próximo do armazém (armazéns não têm caminhões proprietários — `factory_id` é o único vínculo de propriedade). Se encontrar, cria evento `contract_proposal` via EventRepository. Se não encontrar, loga warning — a ordem fica `confirmed` com estoque reservado e o engine reavalia no próximo tick via busca de caminhões disponíveis.
- [ ] `reject_order` → chama `WarehouseService.reject_order(order_id, reason)` que:
  - Atualiza PendingOrder status para `rejected`
  - Libera estoque reservado se já havia sido reservado
- [ ] `request_resupply` → cria um `PendingOrder` no banco com:
  - `requester_type = "warehouse"`, `requester_id = entity_id`
  - `target_type = "factory"`, `target_id = payload["from_factory_id"]`
  - `material_id = payload["material_id"]`
  - `quantity_tons = payload["quantity_tons"]`
  - `status = "pending"`
- [ ] Deduplicação: mesmo critério — skip se já existe PendingOrder ativo do mesmo requester para o mesmo material e target

#### FactoryAgent decisions

- [ ] `start_production` → chama `FactoryRepository.update_production_rate(factory_id, material_id, production_rate)` para ligar/aumentar a produção
- [ ] `send_stock` → cria um `PendingOrder` no banco com:
  - `requester_type = "factory"`, `requester_id = entity_id`
  - `target_type = "warehouse"`, `target_id = payload["destination_warehouse_id"]`
  - `material_id = payload["material_id"]`
  - `quantity_tons = payload["quantity_tons"]`
  - `status = "pending"`
  - Publica evento `new_order` para caminhão proprietário da fábrica, ou `contract_proposal` para caminhão terceiro disponível

#### TruckAgent decisions

- [ ] `accept_contract` → chama `RouteService.compute_route()` + `RouteService.create_route()` + `TruckService.assign_route(truck_id, route_id, cargo)` para colocar o caminhão em trânsito
- [ ] `refuse_contract` → publica evento para que outro caminhão seja avaliado (re-enqueue do contract_proposal)
- [ ] `request_maintenance` → chama `TruckService.schedule_maintenance(truck_id)`

### Backend — Integração com o Grafo LangGraph

- [ ] O nó `act` em `base.py` chama `DecisionEffectProcessor.process()` **após** persistir a decisão no `AgentDecisionRepository` e **antes** de publicar no Redis
- [ ] O `DecisionEffectProcessor` recebe a mesma `db_session` do agente — os efeitos rodam na mesma transação
- [ ] `build_agent_graph()` aceita o processor como parâmetro e injeta no `act` node
- [ ] Cada agente concreto (`StoreAgent`, `WarehouseAgent`, `FactoryAgent`, `TruckAgent`) instancia o processor ao criar o grafo

### Backend — Deduplicação de Ordens

- [ ] `OrderRepository` ganha método `has_active_order(requester_id: str, material_id: str, target_id: str | None = None) -> bool` que verifica se existe PendingOrder com status em `("pending", "confirmed")` para o par requester+material (e opcionalmente target)
- [ ] O processor consulta `has_active_order` antes de criar qualquer PendingOrder novo — se existe, loga skip e retorna sem criar

### Backend — Criação de Eventos para Caminhões

- [ ] Quando uma ordem é confirmada pelo armazém e envolve transporte (qualquer ordem com origem e destino físicos diferentes), o processor cria um `ChaosEvent` com `event_type = "new_order"` (proprietário) ou `"contract_proposal"` (terceiro) vinculado a um caminhão disponível
- [ ] Seleção de caminhão: prioriza caminhão `idle` vinculado à fábrica/armazém de origem (proprietário), senão busca terceiro `idle` mais próximo
- [ ] Se nenhum caminhão disponível, loga warning — a ordem fica pendente e será reavaliada no próximo tick

### Testes

- [ ] `test_process_order_replenishment_creates_pending_order` — StoreAgent decide `order_replenishment` → PendingOrder criado com campos corretos
- [ ] `test_process_order_replenishment_deduplicates` — segunda chamada com mesmo requester+material → PendingOrder **não** duplicado
- [ ] `test_process_confirm_order_updates_status` — WarehouseAgent decide `confirm_order` → PendingOrder status muda para `confirmed`
- [ ] `test_process_reject_order_updates_status` — WarehouseAgent decide `reject_order` → PendingOrder status muda para `rejected`
- [ ] `test_process_request_resupply_creates_order_to_factory` — WarehouseAgent decide `request_resupply` → PendingOrder criado com target_type=factory
- [ ] `test_process_send_stock_creates_order_and_truck_event` — FactoryAgent decide `send_stock` → PendingOrder criado + evento para caminhão
- [ ] `test_process_accept_contract_assigns_route` — TruckAgent decide `accept_contract` → rota criada + caminhão em trânsito
- [ ] `test_process_request_maintenance_schedules` — TruckAgent decide `request_maintenance` → caminhão em manutenção
- [ ] `test_process_hold_is_noop` — qualquer agente decide `hold` → nenhum side-effect
- [ ] `test_process_unknown_action_logs_warning` — ação desconhecida → log warning, sem crash
- [ ] `test_process_confirm_order_dispatches_truck` — WarehouseAgent decide `confirm_order` → além de confirmar, evento `contract_proposal` criado para caminhão terceiro idle
- [ ] `test_process_confirm_order_no_truck_available_logs_warning` — nenhum caminhão idle disponível → decisão confirmada normalmente, nenhum evento criado, warning logado
- [ ] `test_effect_failure_does_not_block_decision_persistence` — se o handler falha, a decisão continua persistida

---

## Fora do Escopo

- Modificar os prompts dos agentes — os prompts já descrevem as ações corretas
- Modificar os guardrails — a validação de payload já existe
- Implementar logic de retry automático para ordens rejeitadas — pode ser feature futura
- Implementar leilão de contratos para caminhões terceiros — simplificado para seleção do mais próximo
- Dashboard/frontend para visualizar o fluxo de ordens — feature futura
