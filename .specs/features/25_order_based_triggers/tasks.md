# Tasks — Feature 25: Order-Based Triggers

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — arquitetura do MAS (§4.2), simulacao e caos (§4.4), fluxo de decisao (§7), TDD (§9), convencoes (§8)
- `.specs/features/25_order_based_triggers/specs.md` — criterios de aceitacao desta feature
- `backend/src/simulation/engine.py` — `SimulationEngine._evaluate_triggers()` (linhas 212-301) e `_apply_physics()` — para entender a estrutura atual dos triggers
- `backend/src/simulation/events.py` — `SimulationEvent` dataclass, `trigger_event()`, constantes de event types
- `backend/src/repositories/order.py` — `OrderRepository` metodos existentes: `get_pending_for_target`, `update_status`, `increment_all_age_ticks`
- `backend/src/database/models/order.py` — schema do `PendingOrder` (colunas existentes)
- `backend/src/agents/prompts/warehouse.md` — gatilhos `stock_projection`, `order_received`, `resupply_delivered`
- `backend/src/agents/prompts/factory.md` — gatilhos `stock_projection`, `resupply_requested`, `machine_breakdown`
- `backend/src/world/state.py` — `WorldState` e suas entidades
- `backend/src/services/trigger_evaluation.py` — se existir, para referencia de como triggers sao avaliados

Nao leia specs de outras features. Nao modifique prompts nem guardrails.

---

## Plano de Execucao

**Fase 1 (TDD) — Grupo 1:** escrever todos os testes antes de qualquer implementacao. Parar e aguardar aprovacao.

**Fase 2 (Implementacao) — Grupos 2-5** apos aprovacao dos testes.

---

### Grupo 1 — Testes (FASE 1: TDD) PARAR AQUI

**Tarefa:** Escrever todos os testes unitarios e de integracao. Nao escrever nenhum codigo de implementacao.

**Estrutura de pastas dos testes:**

```
backend/tests/unit/repositories/
├── __init__.py
├── test_order_repository.py          # testes dos novos metodos

backend/tests/unit/simulation/
├── __init__.py
├── test_engine_order_triggers.py     # testes dos triggers no engine

backend/tests/unit/simulation/
├── test_events.py                    # testes do novo event builder (se necessario)
```

Criar `__init__.py` em todos os subdiretorios se nao existirem.

**Fixtures compartilhadas** para `test_order_repository.py`:

- `mock_session` — `AsyncMock` de `AsyncSession` com `execute` retornando `MagicMock` com `scalars().all()` configuravel
- `order_repo` — `OrderRepository(mock_session)`
- `sample_pending_order` — `MagicMock` simulando PendingOrder com `id=uuid4()`, `status="pending"`, `triggered_at_tick=None`, `target_id="wh_01"`, `material_id="cimento"`, `quantity_tons=20`, `requester_type="store"`, `requester_id="store_01"`

**Testes em `test_order_repository.py`:**

1. `test_get_untriggered_for_target_returns_pending_only` — configura mock para retornar lista com 1 ordem pendente + 1 confirmada. Verifica que o SQL gerado filtra por `status="pending"` e `triggered_at_tick IS NULL`. Como e teste unitario com mock, validar que `select()` e chamado com os filtros corretos (ou testar via integracao).
2. `test_get_untriggered_for_target_excludes_triggered` — configura mock para retornar lista vazia quando todas as ordens tem `triggered_at_tick != None`. Verifica que o resultado e lista vazia.
3. `test_mark_triggered_sets_tick` — chama `mark_triggered(order_id, 10)` — verifica que `session.execute` foi chamado com UPDATE que seta `triggered_at_tick=10` para o `order_id` dado.
4. `test_get_triggered_but_pending_for_target` — configura mock para retornar ordens com `status="pending"` e `triggered_at_tick IS NOT NULL` — verifica que o metodo retorna apenas essas ordens.
5. `test_reset_triggered` — chama `reset_triggered(order_id)` — verifica que `session.execute` foi chamado com UPDATE que seta `triggered_at_tick=None`.

**Fixtures compartilhadas** para `test_engine_order_triggers.py`:

- `mock_session_factory` — context manager async que retorna `mock_session`
- `mock_session` — `AsyncMock` de `AsyncSession`
- `mock_publisher_redis` — `AsyncMock`
- `engine` — `SimulationEngine(mock_publisher_redis, mock_session_factory)`
- `sample_world_state` — `MagicMock` de `WorldState` com:
  - `warehouses`: lista com 1 armazem (`id="wh_01"`, stocks com 1 material acima do min_stock para que o trigger de estoque NAO dispare)
  - `factories`: lista com 1 fabrica (`id="factory_01"`, products com estoque acima de 30%)
  - `stores`: lista vazia
  - `trucks`: lista vazia
- `mock_order_repo` — `AsyncMock` de `OrderRepository` (patcheado dentro do teste via `unittest.mock.patch`)
- `mock_event_repo` — `AsyncMock` de `EventRepository` com `get_active_for_entity` retornando `[]`

**Testes em `test_engine_order_triggers.py`:**

1. `test_evaluate_triggers_fires_order_received_for_warehouse` — patcha `OrderRepository.get_untriggered_for_target` para retornar 1 PendingOrder pendente com `target_id="wh_01"` → resultado de `_evaluate_triggers` contem trigger com `event_type="order_received"` e `entity_id="wh_01"`
2. `test_evaluate_triggers_fires_resupply_requested_for_factory` — patcha `OrderRepository.get_untriggered_for_target` para retornar 1 PendingOrder com `target_id="factory_01"` → trigger com `event_type="resupply_requested"` e `entity_id="factory_01"`
3. `test_evaluate_triggers_marks_order_as_triggered` — patcha `OrderRepository.get_untriggered_for_target` retornando 1 ordem → verifica que `OrderRepository.mark_triggered` foi chamado com `(order.id, current_tick)`
4. `test_evaluate_triggers_skips_already_triggered_orders` — patcha `OrderRepository.get_untriggered_for_target` retornando lista vazia (simula que todas as ordens ja foram triggered) → nenhum trigger de `order_received` no resultado
5. `test_evaluate_triggers_warehouse_both_stock_and_order_triggers` — armazem com estoque <= 120% do min_stock (dispara `stock_trigger_warehouse`) E com ordem pendente (dispara `order_received`) → resultado contem 2 triggers para o mesmo armazem com event types diferentes
6. `test_evaluate_triggers_multiple_orders_for_same_target` — patcha `OrderRepository.get_untriggered_for_target` retornando 2 ordens para `wh_01` → resultado contem 2 triggers `order_received` separados, cada um com payload de uma ordem diferente
7. `test_evaluate_triggers_order_payload_contains_order_data` — verifica que o `SimulationEvent.payload` do trigger contem: `order_id` (str), `requester_type`, `requester_id`, `material_id`, `quantity_tons`
8. `test_evaluate_triggers_no_pending_orders_no_extra_triggers` — patcha `get_untriggered_for_target` retornando `[]` para todos → resultado so contem os triggers de estoque existentes (se houver), sem triggers de ordem
9. `test_evaluate_triggers_resets_triggered_for_fulfillable_factory_order` — fabrica com `factory_product.stock=100` e PendingOrder com `triggered_at_tick=5`, `status="pending"`, `quantity_tons=50` → `OrderRepository.reset_triggered` chamado
10. `test_evaluate_triggers_does_not_reset_if_insufficient_stock` — fabrica com `factory_product.stock=10` e PendingOrder com `quantity_tons=50` → `reset_triggered` nao chamado

**PARAR apos criar os testes. Nao escrever nenhum codigo de implementacao. Aguardar aprovacao do usuario.**

---

### Grupo 2 — Model e Migration (FASE 2)

**Tarefa:** Adicionar o campo `triggered_at_tick` ao `PendingOrder`.

1. Editar `backend/src/database/models/order.py`:
   - Adicionar `triggered_at_tick = Column(Integer, nullable=True, default=None)` ao `PendingOrder`

2. Gerar migration com Alembic:
   - `alembic revision --autogenerate -m "add triggered_at_tick to pending_orders"`
   - Verificar que a migration so contem `add_column` para `triggered_at_tick`
   - Rodar: `alembic upgrade head`

---

### Grupo 3 — Repository (FASE 2)

**Tarefa:** Adicionar os novos metodos ao `OrderRepository`.

1. Editar `backend/src/repositories/order.py`:

   - Adicionar `async def get_untriggered_for_target(self, target_id: str) -> list[PendingOrder]`:
     ```python
     result = await self._session.execute(
         select(PendingOrder).where(
             PendingOrder.target_id == target_id,
             PendingOrder.status == "pending",
             PendingOrder.triggered_at_tick.is_(None),
         )
     )
     return result.scalars().all()
     ```

   - Adicionar `async def mark_triggered(self, order_id: UUID, tick: int) -> None`:
     ```python
     await self._session.execute(
         update(PendingOrder)
         .where(PendingOrder.id == order_id)
         .values(triggered_at_tick=tick)
     )
     ```

   - Adicionar `async def get_triggered_but_pending_for_target(self, target_id: str) -> list[PendingOrder]`:
     ```python
     result = await self._session.execute(
         select(PendingOrder).where(
             PendingOrder.target_id == target_id,
             PendingOrder.status == "pending",
             PendingOrder.triggered_at_tick.isnot(None),
         )
     )
     return result.scalars().all()
     ```

   - Adicionar `async def reset_triggered(self, order_id: UUID) -> None`:
     ```python
     await self._session.execute(
         update(PendingOrder)
         .where(PendingOrder.id == order_id)
         .values(triggered_at_tick=None)
     )
     ```

---

### Grupo 4 — Events (FASE 2)

**Tarefa:** Adicionar constantes e estender a funcao de criacao de eventos.

1. Editar `backend/src/simulation/events.py`:

   - Adicionar constantes:
     ```python
     ORDER_RECEIVED = "order_received"
     RESUPPLY_REQUESTED = "resupply_requested"
     ```

   - Estender `trigger_event()` para aceitar payload opcional:
     ```python
     def trigger_event(
         entity_type: str, entity_id: str, event_type: str, tick: int,
         payload: dict | None = None,
     ) -> SimulationEvent:
         return SimulationEvent(
             event_type=event_type,
             source="engine",
             entity_type=entity_type,
             entity_id=entity_id,
             payload=payload or {},
             tick=tick,
         )
     ```
     Isso e backwards-compatible — chamadas existentes sem `payload` continuam funcionando.

---

### Grupo 5 — Engine Triggers (FASE 2)

**Tarefa:** Integrar a deteccao de ordens no `_evaluate_triggers()`.

1. Editar `backend/src/simulation/engine.py`:

   - Importar `ORDER_RECEIVED` e `RESUPPLY_REQUESTED` de `src.simulation.events`

   - No metodo `_evaluate_triggers()`, dentro do `async with self._session_factory() as session:`, apos o loop de armazens (stock triggers):

     ```python
     # Order-based triggers for warehouses
     for warehouse in world_state.warehouses:
         untriggered_orders = await order_repo.get_untriggered_for_target(warehouse.id)
         for order in untriggered_orders:
             order_payload = {
                 "order_id": str(order.id),
                 "requester_type": order.requester_type,
                 "requester_id": order.requester_id,
                 "material_id": order.material_id,
                 "quantity_tons": order.quantity_tons,
             }
             triggers.append(
                 (
                     self._make_agent_callable("warehouse", warehouse.id),
                     trigger_event(
                         "warehouse", warehouse.id, ORDER_RECEIVED, self._tick,
                         payload=order_payload,
                     ),
                 )
             )
             await order_repo.mark_triggered(order.id, self._tick)
     ```

   - Apos o loop de fabricas (stock triggers), adicionar bloco analogo:

     ```python
     # Order-based triggers for factories
     for factory in world_state.factories:
         untriggered_orders = await order_repo.get_untriggered_for_target(factory.id)
         for order in untriggered_orders:
             order_payload = {
                 "order_id": str(order.id),
                 "requester_type": order.requester_type,
                 "requester_id": order.requester_id,
                 "material_id": order.material_id,
                 "quantity_tons": order.quantity_tons,
             }
             triggers.append(
                 (
                     self._make_agent_callable("factory", factory.id),
                     trigger_event(
                         "factory", factory.id, RESUPPLY_REQUESTED, self._tick,
                         payload=order_payload,
                     ),
                 )
             )
             await order_repo.mark_triggered(order.id, self._tick)
     ```

   - **Re-trigger de fabricas com estoque suficiente (anti-deadlock):** apos os triggers de `resupply_requested`, adicionar:

     ```python
     # Re-trigger factories that now have stock to fulfill pending orders
     for factory in world_state.factories:
         triggered_orders = await order_repo.get_triggered_but_pending_for_target(factory.id)
         for order in triggered_orders:
             factory_product = next(
                 (p for mid, p in factory.products.items() if mid == order.material_id),
                 None,
             )
             if factory_product and factory_product.stock >= order.quantity_tons:
                 await order_repo.reset_triggered(order.id)
     ```

     Isso reseta `triggered_at_tick` para ordens que a fabrica agora pode atender. No proximo tick, a ordem sera detectada por `get_untriggered_for_target` e dispara `resupply_requested` novamente.

   - Instanciar `OrderRepository(session)` como `order_repo` no inicio do bloco `async with` (ja existe para o `_apply_physics` — verificar se existe no `_evaluate_triggers`; se nao, adicionar)

   - Adicionar `await session.commit()` ao final do bloco para persistir os `mark_triggered` e `reset_triggered`

---

### Grupo 6 — Validacao e Finalizacao (sequencial, apos Grupos 2-5)

**Tarefa:** Rodar testes e atualizar state.

1. Rodar os testes novos:
   - `pytest backend/tests/unit/repositories/test_order_repository.py -v`
   - `pytest backend/tests/unit/simulation/test_engine_order_triggers.py -v`
   - Corrigir qualquer falha antes de avancar

2. Rodar testes existentes para garantir nao-regressao:
   - `pytest backend/tests/unit/simulation/ -v`
   - `pytest backend/tests/unit/agents/ -v`
   - `pytest backend/tests/integration/ -v` (se banco disponivel)

3. Verificar que `trigger_event()` com `payload` default nao quebra chamadas existentes — buscar todas as chamadas a `trigger_event()` no codebase e confirmar que nenhuma passa `payload` como argumento posicional.

4. Atualizar `state.md`: adicionar feature 25 na tabela com status adequado.

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos.
Todos os testes novos passam com `pytest`.
Testes existentes de engine e agentes continuam passando (nao-regressao).
`trigger_event()` e backwards-compatible.
`state.md` atualizado com feature 25 como `done`.
