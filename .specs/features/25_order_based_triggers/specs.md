# Feature 25 — Order-Based Triggers

## Objetivo

Fecha a lacuna entre a criacao de PendingOrders (feature 24) e o despertar dos agentes que devem processa-las. Hoje, o engine `_evaluate_triggers()` so detecta gatilhos baseados em **niveis de estoque** — nunca verifica se existem PendingOrders novas direcionadas a armazens ou fabricas. Resultado: um armazem recebe um pedido de uma loja, mas nunca e acordado para processa-lo. Uma fabrica recebe um pedido de reposicao de um armazem, mas nunca e informada.

### Problema Concreto

1. **Armazem nunca processa pedidos de lojas:** O prompt do warehouse define o gatilho `order_received`, mas o engine nunca dispara esse gatilho. O armazem so acorda quando seu proprio estoque esta baixo (`stock_trigger_warehouse`). PendingOrders com `target_type="warehouse"` ficam em `pending` indefinidamente.
2. **Fabrica nunca processa pedidos de armazens:** O prompt do factory define o gatilho `resupply_requested`, mas o engine nunca dispara esse gatilho. A fabrica so acorda quando seu proprio estoque esta abaixo de 30% com producao parada. PendingOrders com `target_type="factory"` ficam em `pending` indefinidamente.
3. **Re-trigger infinito:** Sem mecanismo de controle, o engine dispararia o mesmo trigger para a mesma ordem a cada tick enquanto ela permanecesse `pending`. O agente receberia o mesmo pedido repetidamente, gerando decisoes duplicadas.

### Solucao

1. Adicionar campo `triggered_at_tick` (nullable Integer) ao model `PendingOrder` — quando o engine dispara um trigger para uma ordem, grava o tick atual. Ordens com `triggered_at_tick IS NOT NULL` sao ignoradas nos proximos ticks.
2. Adicionar metodo `get_untriggered_for_target(target_id)` ao `OrderRepository` — retorna PendingOrders com `status="pending"` e `triggered_at_tick IS NULL` para o target dado.
3. Adicionar metodo `mark_triggered(order_id, tick)` ao `OrderRepository` — seta `triggered_at_tick` para o tick dado.
4. No engine `_evaluate_triggers()`, apos os triggers de estoque existentes:
   - Para cada armazem: busca ordens nao-triggeredas com `target_id == warehouse.id` → dispara `order_received` com payload contendo os dados da ordem.
   - Para cada fabrica: busca ordens nao-triggeredas com `target_id == factory.id` → dispara `resupply_requested` com payload contendo os dados da ordem.
   - Marca cada ordem processada como triggered.
5. Adicionar novos event type constants em `events.py`: `ORDER_RECEIVED` e `RESUPPLY_REQUESTED`.

---

## Criterios de Aceitacao

### Backend — Model `PendingOrder`

- [ ] `PendingOrder` ganha coluna `triggered_at_tick` — `Column(Integer, nullable=True, default=None)`
- [ ] Alembic migration gerada para adicionar a coluna (ou manual ALTER se apropriado para a fase do projeto)

### Backend — `OrderRepository`

- [ ] `OrderRepository.get_untriggered_for_target(target_id: str) -> list[PendingOrder]` retorna ordens com `status="pending"` AND `triggered_at_tick IS NULL` AND `target_id == target_id`
- [ ] `OrderRepository.mark_triggered(order_id: UUID, tick: int) -> None` executa `UPDATE pending_orders SET triggered_at_tick = tick WHERE id = order_id`
- [ ] `OrderRepository.get_untriggered_for_target` nao retorna ordens com status `confirmed`, `rejected`, `delivered` ou `cancelled`
- [ ] `OrderRepository.get_untriggered_for_target` nao retorna ordens que ja foram triggered (triggered_at_tick IS NOT NULL)

### Backend — `simulation/events.py`

- [ ] Constante `ORDER_RECEIVED = "order_received"` adicionada
- [ ] Constante `RESUPPLY_REQUESTED = "resupply_requested"` adicionada
- [ ] Funcao `trigger_event()` continua funcionando — os novos event types sao strings como os existentes

### Backend — `SimulationEngine._evaluate_triggers()`

- [ ] Apos avaliar triggers de estoque dos armazens, para cada armazem: chama `OrderRepository.get_untriggered_for_target(warehouse.id)`
- [ ] Para cada ordem retornada: cria trigger event com `event_type = ORDER_RECEIVED` e `payload` contendo `order_id`, `requester_type`, `requester_id`, `material_id`, `quantity_tons`
- [ ] Chama `OrderRepository.mark_triggered(order.id, current_tick)` para evitar re-trigger
- [ ] Apos avaliar triggers de estoque das fabricas, para cada fabrica: chama `OrderRepository.get_untriggered_for_target(factory.id)`
- [ ] Para cada ordem retornada: cria trigger event com `event_type = RESUPPLY_REQUESTED` e `payload` contendo `order_id`, `requester_type`, `requester_id`, `material_id`, `quantity_tons`
- [ ] Chama `OrderRepository.mark_triggered(order.id, current_tick)` para evitar re-trigger

#### Re-trigger de fabricas com estoque suficiente (anti-deadlock producao→despacho)

- [ ] Apos os triggers de `resupply_requested` (ordens novas), para cada fabrica: verifica se existem PendingOrders com `triggered_at_tick IS NOT NULL` e `status = "pending"` onde a fabrica agora tem estoque suficiente do material solicitado (`factory_product.stock >= order.quantity_tons`)
- [ ] `OrderRepository` ganha metodo `get_triggered_but_pending_for_target(target_id: str) -> list[PendingOrder]` — retorna ordens com `status="pending"` e `triggered_at_tick IS NOT NULL`
- [ ] Para cada ordem fulfillable: reseta `triggered_at_tick = None` via `OrderRepository.reset_triggered(order_id)` para que ela seja re-triggereada como `resupply_requested` no proximo tick
- [ ] Isso resolve o deadlock: fabrica recebe `resupply_requested` → decide `start_production` → producao roda → estoque cresce → engine detecta que a ordem pode ser atendida → reseta trigger → fabrica re-acorda → decide `send_stock`

- [ ] Um armazem pode ter tanto trigger de estoque baixo quanto trigger de `order_received` no mesmo tick — ambos sao disparados, o armazem recebe dois eventos separados
- [ ] Se multiplas ordens pendentes para o mesmo target, cada uma gera um trigger separado (o agente recebe uma por vez — o engine cria um callable por ordem)
- [ ] O `trigger_event()` de `events.py` e estendido ou complementado para aceitar payload — atualmente `trigger_event()` sempre envia `payload={}`, os novos triggers precisam de payload com dados da ordem

### Backend — Extensao de `trigger_event()` ou nova funcao

- [ ] Criar funcao `order_trigger_event(entity_type, entity_id, event_type, order_data, tick) -> SimulationEvent` que inclui os dados da ordem no `payload`, OU estender `trigger_event()` com parametro opcional `payload: dict = {}`
- [ ] O payload deve conter no minimo: `order_id` (str do UUID), `requester_type`, `requester_id`, `material_id`, `quantity_tons`

### Testes

- [ ] `test_get_untriggered_for_target_returns_pending_only` — `get_untriggered_for_target` retorna apenas ordens com status `pending` e `triggered_at_tick IS NULL`
- [ ] `test_get_untriggered_for_target_excludes_triggered` — ordem com `triggered_at_tick=5` nao e retornada
- [ ] `test_get_untriggered_for_target_excludes_non_pending` — ordens com status `confirmed`, `rejected`, `delivered` nao sao retornadas
- [ ] `test_mark_triggered_sets_tick` — apos `mark_triggered(order_id, 10)`, a ordem tem `triggered_at_tick=10`
- [ ] `test_evaluate_triggers_fires_order_received_for_warehouse` — armazem com PendingOrder pendente nao-triggered → trigger `order_received` aparece na lista de triggers com payload contendo dados da ordem
- [ ] `test_evaluate_triggers_fires_resupply_requested_for_factory` — fabrica com PendingOrder pendente nao-triggered → trigger `resupply_requested` aparece na lista de triggers
- [ ] `test_evaluate_triggers_marks_order_as_triggered` — apos avaliar, a ordem tem `triggered_at_tick` setado para o tick atual
- [ ] `test_evaluate_triggers_skips_already_triggered_orders` — ordem com `triggered_at_tick` ja setado nao gera trigger novamente
- [ ] `test_evaluate_triggers_warehouse_can_have_both_stock_and_order_triggers` — armazem com estoque baixo E ordem pendente → dois triggers na lista (um `stock_trigger_warehouse`, outro `order_received`)
- [ ] `test_evaluate_triggers_multiple_orders_generate_multiple_triggers` — duas ordens pendentes para o mesmo armazem → dois triggers `order_received` separados
- [ ] `test_order_trigger_event_includes_payload` — o SimulationEvent gerado contem `payload` com `order_id`, `material_id`, `quantity_tons`
- [ ] `test_evaluate_triggers_resets_triggered_for_fulfillable_factory_order` — fabrica com PendingOrder triggered (status=pending, triggered_at_tick=5) e estoque suficiente → `reset_triggered` chamado, ordem volta a ser elegivel para trigger no proximo tick
- [ ] `test_evaluate_triggers_does_not_reset_if_insufficient_stock` — fabrica com PendingOrder triggered mas estoque insuficiente → `reset_triggered` nao chamado

---

## Fora do Escopo

- Trigger `resupply_delivered` — depende de Feature 26 (delivery completion). A infraestrutura de trigger para ordens esta pronta aqui; o evento concreto de entrega sera criado na Feature 26.
- Modificar prompts dos agentes — os prompts ja definem `order_received` e `resupply_requested` como gatilhos reconhecidos
- Modificar guardrails — a validacao de decisoes nao muda
- Logica de re-trigger apos timeout (ex: ordem pendente por mais de N ticks sem decisao) — feature futura
- Frontend para visualizar triggers — feature futura
