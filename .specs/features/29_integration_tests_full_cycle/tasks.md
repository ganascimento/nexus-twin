# Tasks — Feature 29: Integration Tests Full Cycle

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — TDD (§9), convencoes (§8), constraints (§9)
- `.specs/features/29_integration_tests_full_cycle/specs.md` — cenarios e criterios
- `backend/tests/integration/simulation/conftest.py` — fixtures existentes: `seeded_simulation_client`, `mock_redis`, `advance_n_ticks`
- `backend/tests/integration/simulation/test_agent_e2e.py` — testes existentes como referencia de padrao
- `backend/tests/integration/conftest.py` — `client`, `seeded_client`
- `backend/src/database/seed.py` — dados do mundo padrao
- `.specs/prd.md` §4 — dados do seed (estoques, capacidades, localizacoes)

**Pre-requisito:** F24-F28 devem estar implementados. Se alguma feature ainda nao foi implementada, os testes correspondentes vao falhar — isso e esperado e desejavel (TDD).

---

## Plano de Execucao

**Esta feature nao tem Fase 2.** E 100% testes. Nao implementa codigo de producao.

**Grupo 1:** Helpers e fixtures
**Grupos 2-5:** Testes por cenario (podem ser paralelos)
**Grupo 6:** Validacao

---

### Grupo 1 — Helpers e Fixtures

**Tarefa:** Criar fixtures compartilhadas para os testes de ciclo completo.

1. Editar `backend/tests/integration/simulation/conftest.py` — adicionar:

   ```python
   from unittest.mock import patch, AsyncMock
   from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
   from langchain_core.messages import AIMessage

   VALHALLA_MOCK_ROUTE = {
       "path": [[-46.6, -23.5], [-46.7, -23.4], [-46.8, -23.3], [-46.9, -23.2], [-47.0, -23.1]],
       "timestamps": [0, 1, 2, 3, 4],
       "distance_km": 100.0,
       "eta_ticks": 3,
   }

   def make_llm_responses(*response_dicts):
       """Cria FakeMessagesListChatModel com lista de respostas JSON."""
       return FakeMessagesListChatModel(
           responses=[AIMessage(content=json.dumps(r)) for r in response_dicts]
       )

   async def advance_ticks_with_settle(client, n: int, settle_time: float = 2.0):
       """Avanca N ticks com tempo para agents fire-and-forget completarem."""
       for _ in range(n):
           await client.post("/simulation/tick")
           await asyncio.sleep(0.3)
       await asyncio.sleep(settle_time)

   async def get_order_status(session, order_id) -> str:
       result = await session.execute(
           text("SELECT status FROM pending_orders WHERE id = :id"),
           {"id": str(order_id)}
       )
       return result.scalar_one()

   async def get_truck_status(session, truck_id) -> str:
       result = await session.execute(
           text("SELECT status FROM trucks WHERE id = :id"),
           {"id": truck_id}
       )
       return result.scalar_one()

   async def get_stock(session, table, entity_id_col, entity_id, material_id) -> float:
       result = await session.execute(
           text(f"SELECT stock FROM {table} WHERE {entity_id_col} = :eid AND material_id = :mid"),
           {"eid": entity_id, "mid": material_id}
       )
       return result.scalar_one()
   ```

2. Criar fixture `mock_valhalla`:
   ```python
   @pytest.fixture
   def mock_valhalla():
       with patch("src.services.route.RouteService.compute_route", new_callable=AsyncMock) as mock:
           mock.return_value = VALHALLA_MOCK_ROUTE
           yield mock
   ```

---

### Grupo 2 — Cenarios 1 e 2: Ciclo Completo

**Arquivo:** `backend/tests/integration/simulation/test_full_cycle.py`

**Cenario 1 — Happy path (Store→Warehouse→Truck→Store):**

```python
async def test_full_cycle_store_to_delivery(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    # Setup: store-001 cimento baixo
    await session.execute(text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'"))
    await session.commit()

    # Programar respostas LLM na ordem: store → warehouse → truck
    llm = make_llm_responses(
        # Tick 1: store decides
        {"action": "order_replenishment", "payload": {"material_id": "cimento", "quantity_tons": 30, "from_warehouse_id": "warehouse-002"}, "reasoning_summary": "Low stock"},
        # Tick 2: warehouse decides
        {"action": "confirm_order", "payload": {"order_id": "DYNAMIC", "quantity_tons": 30, "eta_ticks": 3}, "reasoning_summary": "Confirmed"},
        # Tick 3: truck decides
        {"action": "accept_contract", "payload": {"order_id": "DYNAMIC", "chosen_route_risk_level": "low"}, "reasoning_summary": "Accepted"},
    )

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        # Tick 1: store order
        await advance_ticks_with_settle(client, 1)
        # Verify PendingOrder created
        ...

        # Tick 2: warehouse confirm + truck dispatch
        await advance_ticks_with_settle(client, 1)
        # Verify order confirmed, stock reserved
        ...

        # Tick 3: truck accepts
        await advance_ticks_with_settle(client, 1)
        # Verify route created, truck in_transit
        ...

        # Ticks 4-6: physics moves truck (ETA=3)
        await advance_ticks_with_settle(client, 3)

    # Final verification
    await session.rollback()

    # Store stock increased
    store_stock = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    assert store_stock >= 31.0  # 1.0 original + 30.0 delivered (minus demand consumption)

    # Order delivered
    result = await session.execute(text("SELECT status FROM pending_orders WHERE requester_id='store-001' AND material_id='cimento' ORDER BY created_at DESC LIMIT 1"))
    assert result.scalar_one() == "delivered"

    # Truck idle
    truck_status = await get_truck_status(session, "truck-004")
    assert truck_status == "idle"
```

**Nota:** os `order_id` dinamicos precisam de tratamento especial. O teste pode:
- Consultar o banco apos tick 1 para obter o order_id real
- Usar o order_id para programar as respostas seguintes
- Ou programar respostas genericas e verificar pelo estado final

**Cenario 2 — Chain completa (Store→Warehouse→Factory→Warehouse→Store):**

Mesmo padrao mas com mais ticks e mais respostas LLM programadas. Verificar estados intermediarios a cada etapa.

**Testes neste arquivo:**
- [ ] `test_full_cycle_store_to_delivery`
- [ ] `test_pending_order_created_after_store_decision`
- [ ] `test_warehouse_reserves_stock_on_confirm`
- [ ] `test_truck_assigned_route_on_accept`
- [ ] `test_stock_transferred_to_store_on_arrival`
- [ ] `test_order_marked_delivered_on_arrival`
- [ ] `test_full_chain_factory_to_store`
- [ ] `test_factory_stock_decremented_on_send`
- [ ] `test_warehouse_stock_increased_after_factory_delivery`

---

### Grupo 3 — Cenarios 3 e 4: Manutencao e Transport Retry

**Arquivo:** `backend/tests/integration/simulation/test_maintenance_cycle.py`

- [ ] `test_maintenance_entry_and_exit` — truck degradation alta → request_maintenance → status=maintenance → N ticks → status=idle
- [ ] `test_maintenance_duration_matches_degradation` — verifica duracao pela tabela do PRD

**Arquivo:** `backend/tests/integration/simulation/test_transport_retry.py`

- [ ] `test_transport_retry_when_no_truck` — ordem confirmed sem truck idle → coloca truck idle → proximo tick cria evento
- [ ] `test_confirmed_order_not_lost` — ordem confirmed permanece por multiplos ticks sem truck

---

### Grupo 4 — Cenarios 5 e 6: Rejeicao e Breakdown

**Arquivo:** `backend/tests/integration/simulation/test_retry_backoff.py`

- [ ] `test_rejected_order_respects_backoff` — rejeicao em tick X, retry so apos X + retry_after_ticks
- [ ] `test_retry_creates_new_order` — nova PendingOrder criada, antiga permanece rejected

**Arquivo:** `backend/tests/integration/simulation/test_breakdown_cycle.py`

- [ ] `test_breakdown_stops_truck` — mock random → truck broken, cargo mantido, evento criado
- [ ] `test_broken_truck_cargo_not_lost` — cargo permanece

---

### Grupo 5 — Cenarios 7-10: Chaos, Deduplicacao, Concorrencia

**Arquivo:** `backend/tests/integration/simulation/test_chaos_integration.py`

- [ ] `test_chaos_machine_breakdown_triggers_factory` — injecao via API + tick → factory agent decide stop_production
- [ ] `test_production_stopped_after_chaos` — production_rate_current = 0
- [ ] `test_chaos_demand_spike_triggers_store` — injecao + tick → store agent acorda

**Arquivo:** `backend/tests/integration/simulation/test_deduplication.py`

- [ ] `test_store_does_not_duplicate_orders` — 3 ticks com estoque baixo → apenas 1 PendingOrder ativo

**Arquivo:** `backend/tests/integration/simulation/test_concurrency.py`

- [ ] `test_concurrent_orders_atomic_reserve` — 2 stores pedem ao mesmo warehouse → stock_reserved nunca excede disponivel

---

### Grupo 6 — Validacao

1. Rodar todos os testes de integracao: `pytest backend/tests/integration/simulation/ -v --timeout=120`
2. Os testes de F29 podem falhar se F24-F28 nao estiverem implementados — isso e esperado. O objetivo e que passem APOS a implementacao completa.
3. Atualizar state.md

---

## Condicao de Conclusao

Todos os testes de integracao passam com banco real (testcontainers).
O ciclo completo Store→Warehouse→Factory→Truck→Delivery funciona de ponta a ponta.
Manutencao, retry, backoff, breakdown e chaos funcionam integrados.
Deduplicacao e concorrencia verificadas.
state.md atualizado.
