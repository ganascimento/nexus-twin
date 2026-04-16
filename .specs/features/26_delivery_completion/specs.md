# Feature 26 — Delivery Completion

## Objetivo

Fecha o ciclo logistico completo de uma entrega. Hoje, quando um caminhao chega ao destino (ETA = 0 em `_apply_physics()`), o engine marca o caminhao como `idle`, limpa o cargo e completa a rota — mas a carga **desaparece**. O estoque do destino nao e atualizado, a PendingOrder nunca e marcada como `delivered`, e nenhum evento e criado para notificar o agente de destino ou o agente do caminhao.

### Problema Concreto

1. **Carga desaparece:** O cargo do caminhao e setado para `None` na chegada, mas as toneladas transportadas nunca sao adicionadas ao estoque do armazem ou loja de destino. Do ponto de vista do mundo, a mercadoria sumiu.
2. **Ordem nunca conclui:** A PendingOrder que originou o transporte permanece com status `confirmed` indefinidamente — nunca transiciona para `delivered`.
3. **Armazem nunca sabe que recebeu estoque:** O trigger `resupply_delivered` definido no prompt do warehouse nunca e disparado. O armazem nao pode re-avaliar pedidos de lojas que estavam em espera.
4. **Caminhao nunca sabe que chegou:** O trigger `truck_arrived` definido no prompt do truck nunca e disparado pelo engine. O caminhao nao pode decidir seu proximo movimento.

### Solucao

Estender o bloco de chegada em `_apply_physics()` (quando `new_eta == 0`) para executar 4 acoes adicionais, todas deterministicas (sem IA):

1. **Stock transfer:** Ler o cargo do caminhao e adicionar a quantidade ao estoque da entidade de destino da rota.
2. **Order completion:** Encontrar a PendingOrder associada e marca-la como `delivered`.
3. **Destination event:** Criar um evento `resupply_delivered` para a entidade de destino, para que o agente acorde no proximo tick.
4. **Truck event:** Criar um evento `truck_arrived` para o caminhao, para que o agente decida o proximo passo.

A decisao arquitetural chave: tudo isso acontece dentro de `_apply_physics()` porque e **fato fisico**, nao decisao de agente. Caminhao chegou = carga entregue = estoque atualizado. E deterministico e sincrono.

### Pre-requisito: Vincular Route a PendingOrder

O model `Route` nao tem referencia a PendingOrder. Para saber qual ordem marcar como `delivered` quando uma rota completa, ha duas abordagens:
- **Opcao A:** Adicionar campo `order_id` ao model `Route` (FK para `pending_orders.id`, nullable).
- **Opcao B:** Fazer lookup por matching de campos (`dest_type` + `dest_id` + `material_id`).

**Opcao A e preferida** — e um vinculo direto, sem ambiguidade, e o `order_id` ja e conhecido no momento de criacao da rota (Feature 24, `_handle_accept_contract`). A Feature 24 precisa ser ajustada para gravar `order_id` na rota.

### Pre-requisito: Formato do cargo

O campo `cargo` do caminhao (JSONB) ja contem `material_id` e `quantity_tons` — verificado no engine (linhas 141-146 de `_apply_physics`). Formato: `{"material_id": "cimento", "quantity_tons": 50}`. Isso e suficiente para a transferencia de estoque.

---

## Criterios de Aceitacao

### Backend — Model `Route`

- [ ] `Route` ganha coluna `order_id` — `Column(UUID(as_uuid=True), ForeignKey("pending_orders.id"), nullable=True)`
- [ ] Alembic migration gerada para adicionar a coluna
- [ ] `RouteRepository.create()` aceita `order_id` no dict de dados sem mudanca de assinatura

### Backend — `RouteRepository`

- [ ] `RouteRepository.get_active_by_truck(truck_id)` continua funcionando sem alteracao (o `order_id` e apenas um campo adicional no model)

### Backend — Integracao com Feature 24

- [ ] `DecisionEffectProcessor._handle_accept_contract()` passa `order_id` no dict de criacao da rota (via `RouteService.create_route()`)
- [ ] Se a rota nao esta associada a uma ordem (ex: rota manual/teste), `order_id` e `None` — o fluxo de delivery completion pula a etapa de order completion

### Backend — `SimulationEngine._apply_physics()` — Bloco de chegada

- [ ] Quando `new_eta == 0` (caminhao chegou), **antes** de limpar cargo e marcar idle:

#### 1. Stock Transfer

- [ ] Le `truck.cargo` para obter `material_id` e `quantity_tons`
- [ ] Se cargo e `None` ou vazio: pula stock transfer (caminhao vazio)
- [ ] Se `route.dest_type == "warehouse"`: chama `WarehouseRepository.update_stock(route.dest_id, material_id, +quantity_tons)`
- [ ] Se `route.dest_type == "store"`: chama `StoreRepository.update_stock(route.dest_id, material_id, +quantity_tons)`
- [ ] Se `route.dest_type` e outro tipo (ex: "factory"): loga warning e pula (fabricas nao recebem estoque via entrega de caminhao neste modelo)

#### 2. Order Completion

- [ ] Se `route.order_id IS NOT NULL`: chama `OrderRepository.update_status(route.order_id, "delivered")`
- [ ] Se `route.order_id IS NULL`: pula (nao ha ordem associada)

#### 3. Destination Event (`resupply_delivered`)

- [ ] Se `route.dest_type` e `"warehouse"` ou `"store"`: cria `ChaosEvent` via `EventRepository.create()` com:
  - `event_type = "resupply_delivered"`
  - `entity_type = route.dest_type`
  - `entity_id = route.dest_id`
  - `source = "engine"`
  - `status = "active"`
  - `tick_start = current_tick`
  - `payload` contendo `material_id`, `quantity_tons`, `from_truck_id = truck.id`
- [ ] O evento sera capturado pelo `_evaluate_triggers()` no proximo tick via `EventRepository.get_active_for_entity()` (ja existente para trucks — verificar se funciona para warehouses/stores)

#### 4. Truck Event (`truck_arrived`)

- [ ] Cria `ChaosEvent` via `EventRepository.create()` com:
  - `event_type = "truck_arrived"`
  - `entity_type = "truck"`
  - `entity_id = truck.id`
  - `source = "engine"`
  - `status = "active"`
  - `tick_start = current_tick`
  - `payload` contendo `route_id = str(route.id)`, `dest_type = route.dest_type`, `dest_id = route.dest_id`

#### 5. Finalizacao (apos os 4 passos acima)

- [ ] Limpa cargo do caminhao: `truck_repo.set_cargo(truck.id, None)`
- [ ] Atualiza posicao para ultimo waypoint da rota (ja existente)
- [ ] Marca caminhao como idle: `truck_repo.update_status(truck.id, "idle")`
- [ ] Limpa active_route: `truck_repo.set_active_route(truck.id, None)`
- [ ] Marca rota como completed: `route_repo.update_status(route.id, "completed")`

### Backend — `simulation/events.py`

- [ ] Constante `RESUPPLY_DELIVERED = "resupply_delivered"` adicionada (se nao existir de Feature 25)
- [ ] Constante `TRUCK_ARRIVED` ja existe — verificar

### Backend — `_evaluate_triggers()` — Suporte a eventos de warehouse/store

- [ ] `_evaluate_triggers()` ja busca eventos ativos para trucks via `EventRepository.get_active_for_entity("truck", truck.id)`. Verificar se faz o mesmo para warehouses e stores.
- [ ] Se nao: adicionar busca de eventos ativos para cada warehouse e store. Quando `event_type == "resupply_delivered"`, disparar trigger para o agente correspondente.
- [ ] Apos o agente processar o evento, o evento deve ser resolvido (marcado como `resolved`). Isso pode ser responsabilidade do agente no nodo `act` — documentar se necessario.

### Backend — Resolucao de eventos apos processamento

- [ ] O agente de warehouse/truck que processa um evento `resupply_delivered` ou `truck_arrived` deve resolver o evento apos processar (chamar `EventRepository.resolve(event_id, tick)`)
- [ ] Alternativa: o engine resolve o evento apos disparar o trigger — mais simples, evita que o evento re-trigger a cada tick. **Opcao preferida:** o engine resolve o evento imediatamente apos criar o trigger, pois o trigger ja contem o payload completo. O agente nao precisa re-consultar o evento.

### Testes

- [ ] `test_apply_physics_arrival_transfers_stock_to_warehouse` — caminhao com cargo `{"material_id": "cimento", "quantity_tons": 50}` chega ao armazem → `WarehouseRepository.update_stock("wh_01", "cimento", 50)` chamado
- [ ] `test_apply_physics_arrival_transfers_stock_to_store` — caminhao chega a loja → `StoreRepository.update_stock("store_01", "cimento", 30)` chamado
- [ ] `test_apply_physics_arrival_empty_cargo_skips_transfer` — caminhao com `cargo=None` chega → nenhum `update_stock` chamado
- [ ] `test_apply_physics_arrival_marks_order_delivered` — rota com `order_id` → `OrderRepository.update_status(order_id, "delivered")` chamado
- [ ] `test_apply_physics_arrival_no_order_skips_completion` — rota com `order_id=None` → `OrderRepository.update_status` nao chamado
- [ ] `test_apply_physics_arrival_creates_resupply_delivered_event` — caminhao chega ao armazem → `EventRepository.create` chamado com `event_type="resupply_delivered"`, `entity_type="warehouse"`, `entity_id="wh_01"`
- [ ] `test_apply_physics_arrival_creates_truck_arrived_event` — caminhao chega → `EventRepository.create` chamado com `event_type="truck_arrived"`, `entity_type="truck"`, `entity_id=truck.id`
- [ ] `test_apply_physics_arrival_clears_truck_state_after_transfer` — apos stock transfer e event creation, caminhao e marcado idle com cargo=None e active_route=None
- [ ] `test_apply_physics_arrival_order_of_operations` — verifica que stock transfer acontece ANTES de limpar cargo (se cargo e lido antes de ser zerado)
- [ ] `test_route_model_has_order_id` — Route com `order_id` e criado e recuperado corretamente
- [ ] `test_evaluate_triggers_fires_on_resupply_delivered_event` — warehouse com evento ativo `resupply_delivered` → trigger disparado para warehouse agent
- [ ] `test_evaluate_triggers_fires_on_truck_arrived_event` — truck com evento ativo `truck_arrived` → trigger disparado para truck agent (ja coberto parcialmente pelo fluxo existente de eventos de truck)

---

## Fora do Escopo

- Logica de partial delivery (caminhao entrega parte da carga) — sempre entrega completa
- Logica de devolucao ou recusa de carga pela entidade de destino — feature futura
- Dashboard/frontend para visualizar entregas — feature futura
- Logica de resolucao automatica de eventos (`resupply_delivered` / `truck_arrived`) pelo agente — se necessario, documentar e implementar como melhoria futura. A opcao preferida e o engine resolver o evento imediatamente apos criar o trigger.
- Modificar prompts dos agentes — os prompts ja definem `resupply_delivered` e `truck_arrived` como gatilhos reconhecidos
