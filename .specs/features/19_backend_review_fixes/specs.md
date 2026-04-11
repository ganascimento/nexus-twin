# Feature 19 — Backend Code Review & Fixes

> Resultado de um code review exaustivo em todas as camadas do backend.
> Esta feature corrige bugs, inconsistencias, dead code, integracao quebrada e servicos stub que impedem o sistema de funcionar end-to-end.

---

## Escopo

Correcoes organizadas em 7 grupos (G1-G7), ordenados por criticidade.

---

## G1 — Agent State Machine (Critical)

O fluxo `perceive -> fast_path -> decide -> act -> END` tem problemas estruturais que impedem os agentes de funcionar.

### G1.1 — `perceive_node` cria `AsyncSession()` sem bind

**Arquivo:** `backend/src/agents/base.py:83-84`

```python
session = AsyncSession()  # sem engine, sem sessionmaker — crash garantido
repo = AgentDecisionRepository(session)
```

**Fix:** Receber `db_session` via closure (igual ao `_make_act_node_for_graph`) em vez de criar sessao solta. Criar `_make_perceive_node(db_session)` que retorna o node function.

### G1.2 — `fast_path` pula `act_node` — decisao nao persiste

**Arquivo:** `backend/src/agents/base.py:239-242`

```python
graph.add_conditional_edges(
    "fast_path",
    lambda state: END if state["fast_path_taken"] else "decide",
)
```

Quando `fast_path_taken=True`, o grafo vai direto para `END`. A decisao **nao e validada pelo guardrail**, **nao e persistida no banco** e **nao e publicada no Redis**.

**Fix:** Quando `fast_path_taken=True`, redirecionar para `act` (nao `END`). O `act_node` ja sabe validar e persistir. O edge condicional deve ser: `END if fast_path_taken else "decide"` → `"act" if fast_path_taken else "decide"`.

### G1.3 — `fast_path` gera decisao invalida: `emergency_order`

**Arquivo:** `backend/src/agents/base.py:132-137`

```python
"decision": {"action": "emergency_order", "payload": {}}
```

`"emergency_order"` nao e uma action valida em nenhum guardrail (FactoryDecision, WarehouseDecision, StoreDecision, TruckDecision). Vai falhar na validacao do `act_node`.

**Fix:** Mapear a acao correta por `entity_type`:
- `store` → `"order_replenishment"` (com payload minimo valido)
- `warehouse` → `"request_resupply"`
- `factory` → `"start_production"`

### G1.4 — `fast_path` decisions sem `reasoning_summary`

**Arquivo:** `backend/src/agents/base.py:127-137`

Decisoes do fast_path retornam `{"action": ..., "payload": {}}` mas o `AgentDecisionBase` exige `reasoning_summary: str` (campo obrigatorio + validador de string nao-vazia).

**Fix:** Incluir `"reasoning_summary": "fast-path: <motivo>"` em todas as decisoes do fast_path.

### G1.5 — Dead code: `act_node` standalone (linhas 155-181)

**Arquivo:** `backend/src/agents/base.py:155-181`

Funcao `act_node()` nunca e usada — o grafo usa `_make_act_node_for_graph()`. E codigo morto que confunde a leitura.

**Fix:** Remover `act_node()` inteira (linhas 155-181).

### G1.6 — Dead code: `run_master_cycle` standalone

**Arquivo:** `backend/src/agents/master_agent.py:96-111`

`run_master_cycle()` e duplicata incompleta de `run_master_cycle_full()`. Nunca e chamada.

**Fix:** Remover `run_master_cycle()` (linhas 96-111).

### G1.7 — `master_agent` instancia agente sem `entity_id`

**Arquivo:** `backend/src/agents/master_agent.py:38`

```python
agent = agent_factory(trigger.entity_type)
```

Mas todos os agentes (FactoryAgent, WarehouseAgent, etc.) exigem `entity_id` no construtor. O `agent_factory` recebe apenas `entity_type`.

**Fix:** Alterar assinatura para `agent_factory(trigger.entity_type, trigger.entity_id)`. Atualizar `_make_dispatch_agents_node` e `run_master_cycle_full`.

### G1.8 — Publisher protocol incompleto

**Arquivo:** `backend/src/services/__init__.py:12-13`

Protocol `Publisher` define apenas `publish_event()`, mas `act_node` chama `publisher.publish_decision()` (base.py:174/204).

**Fix:** Adicionar `publish_decision` ao protocol:
```python
class Publisher(typing.Protocol):
    async def publish_event(self, event_type: str, payload: dict) -> None: ...
    async def publish_decision(self, entity_id: str, entity_type: str, decision: dict) -> None: ...
```

### G1.9 — Chaos evaluation via LLM desnecessaria

**Arquivo:** `backend/src/agents/master_agent.py:49-74`

Cada tick chama o LLM para perguntar "should chaos be injected?". Isso:
- Gasta tokens a cada tick (custo)
- Trunca WorldState em 500 chars (lossy)
- Silencia excecoes (line 69-70)
- Nao aplica semaphore (sem rate limiting)

CLAUDE.md sec 4.4 especifica regras deterministicas (max 1 evento, cooldown 24 ticks). Nao ha necessidade de LLM.

**Fix:** Substituir por chamada deterministica a `ChaosService.can_inject_autonomous_event()`. Se `True`, injetar tipo aleatorio do catalogo permitido. Remover chamada LLM.

---

## G2 — Services Layer: Stubs & Business Logic Bugs

### G2.1 — 5 services criticos sao stubs vazios

**Arquivos:**
- `backend/src/services/simulation.py` — `# stub`
- `backend/src/services/world_state.py` — `# stub`
- `backend/src/services/trigger_evaluation.py` — `# stub`
- `backend/src/services/route.py` — `# stub`
- `backend/src/services/physics.py` — `# stub`

O `SimulationEngine` depende de `world_state_service.load()` — sem implementacao, o engine nao roda. O `MasterAgent` depende de `TriggerEvaluationService().evaluate_all()` — sem implementacao, triggers nao funcionam.

**Fix:** Implementar os 5 services. Os mais criticos sao `world_state.py` e `trigger_evaluation.py` porque bloqueiam a execucao do engine e do master_agent.

### G2.2 — `WarehouseService.reject_order()` nao libera stock reservado

**Arquivo:** `backend/src/services/warehouse.py:48-51`

```python
async def reject_order(self, order_id, reason: str):
    return await self._order_repo.update_status(
        order_id, status="rejected", rejection_reason=reason
    )
```

`confirm_order()` chama `atomic_reserve_stock()` — marca stock como reservado. Mas `reject_order()` apenas muda o status do pedido sem chamar `release_reserved()`. Stock reservado fica preso para sempre.

**Fix:** Antes de mudar status para "rejected", buscar o order, pegar `target_id`, `material_id`, `quantity_tons` e chamar `self._repo.release_reserved(...)`.

### G2.3 — `WarehouseService.confirm_order()` nao e atomico

**Arquivo:** `backend/src/services/warehouse.py:35-46`

Duas operacoes separadas:
1. `atomic_reserve_stock()` — reserva stock
2. `update_status()` — atualiza pedido para "confirmed"

Se (1) sucede mas (2) falha, stock fica reservado sem pedido confirmado.

**Fix:** Envolver em `session.begin_nested()` ou garantir que falha em (2) faz rollback de (1).

### G2.4 — `WarehouseService.adjust_stock()` nao valida capacidade

**Arquivo:** `backend/src/services/warehouse.py:53-60`

Valida `new_stock < 0` mas nao valida `new_stock > capacity_total`. Inconsistente com `FactoryService.adjust_stock()` que valida `stock_max`.

**Fix:** Buscar `warehouse.capacity_total`, calcular total atual e validar antes de aplicar delta.

### G2.5 — `StoreService.delete_store()` nao cancela orders recebidos

**Arquivo:** `backend/src/services/store.py:28-31`

Cancela `orders_from` (onde store e requester) mas nao cancela orders onde store e target (deliveries em andamento). `FactoryService.delete_factory()` e `WarehouseService.delete_warehouse()` fazem `bulk_cancel_by_target()` — store nao faz.

**Fix:** Adicionar `await self._order_service.cancel_orders_targeting(id, "target_deleted")`.

### G2.6 — `TruckService` — 4 metodos NotImplementedError

**Arquivo:** `backend/src/services/truck.py:37-47`

`assign_route`, `complete_route`, `interrupt_route`, `schedule_maintenance` — todos `raise NotImplementedError`. O engine bypassa o service e chama o repository diretamente.

**Fix:** Implementar os 4 metodos com validacao de negocio e publisher events.

### G2.7 — `OrderService.mark_delivered()` sem null check

**Arquivo:** `backend/src/services/order.py:27-28`

```python
order = await self._repo.get_by_id(order_id)
if order.target_type == "warehouse":  # AttributeError se order is None
```

**Fix:** Adicionar `if order is None: raise NotFoundError(order_id)`.

### G2.8 — Error messages inconsistentes nos services

Padroes diferentes:
- `FactoryService`: `NotFoundError(id)` — so o ID
- `StoreService`: `NotFoundError(f"Store '{id}' not found")` — mensagem formatada
- `WarehouseService`: `NotFoundError(id)` — so o ID
- `TruckService`: `NotFoundError(f"Truck '{id}' not found")` — mensagem formatada

**Fix:** Padronizar: `NotFoundError(f"<EntityType> '{id}' not found")` em todos os services.

---

## G3 — API Layer: Dependencies & Validation

### G3.1 — 6 dependency factories sao NotImplementedError

**Arquivo:** `backend/src/api/dependencies.py`

- `get_simulation_service()`
- `get_world_state_service()`
- `get_factory_service()`
- `get_warehouse_service()`
- `get_store_service()`
- `get_truck_service()`
- `get_chaos_service()`

**Fix:** Implementar todas as factories seguindo o padrao de `get_material_service()`: instanciar repos + service com dependencias corretas.

### G3.2 — CORS inseguro

**Arquivo:** `backend/src/main.py:75-81`

`allow_origins=["*"]` com `allow_credentials=True` viola a spec CORS — browsers rejeitam credenciais com wildcard origin.

**Fix:** Usar `VITE_API_URL` como origin permitido em producao, ou remover `allow_credentials=True` se nao necessario.

### G3.3 — Rotas sem `response_model`

**Arquivos:** `api/routes/simulation.py`, `api/routes/world.py` e outros

Endpoints retornam dicts sem `response_model` — OpenAPI schema incompleto, sem type checking.

**Fix:** Adicionar `response_model` a todos os endpoints GET/POST.

### G3.4 — DELETE endpoints sem `status_code=204`

**Arquivos:** `factories.py:42`, `warehouses.py:42`, `stores.py:42`, `trucks.py:32`

Retornam HTTP 200 com body `{"status": "deleted"}` em vez de 204 No Content.

**Fix:** Adicionar `status_code=204` e `response_class=Response` nos DELETEs.

### G3.5 — Input validation fraca nos request models

**Arquivos:** Todos em `api/models/`

Campos criticos sem validacao:
- `MaterialCreate.name` — aceita string vazia
- `lat/lng` — aceita valores fora de range
- `capacity_total` — aceita negativo
- `tick_interval_seconds` — aceita negativo/zero

**Fix:** Adicionar `Field(min_length=1)`, `Field(ge=-90, le=90)`, `Field(gt=0)` etc.

### G3.6 — `ChaosEventCreate.payload` com mutable default

**Arquivo:** `backend/src/api/models/chaos.py:10`

```python
payload: dict = {}  # mutable default
```

**Fix:** `payload: dict = Field(default_factory=dict)`.

---

## G4 — Simulation Engine Bugs

### G4.1 — `route.eta_ticks` nunca e decrementado

**Arquivo:** `backend/src/simulation/engine.py:88`

```python
if route.eta_ticks == 0:
```

O engine checa `eta_ticks == 0` para determinar se viagem terminou, mas em nenhum momento `eta_ticks` e decrementado. Caminhoes nunca chegam ao destino.

**Fix:** Decrementar `eta_ticks` no inicio do bloco de fisica do truck:
```python
new_eta = max(0, route.eta_ticks - 1)
await route_repo.update_eta_ticks(route.id, new_eta)
```

### G4.2 — `route.active_route` sem null check

**Arquivo:** `backend/src/simulation/engine.py:86`

```python
route = truck.active_route  # pode ser None se lazy loading
```

Se truck esta IN_TRANSIT mas `active_route` nao foi eager-loaded, crash.

**Fix:** Adicionar `if route is None: continue` com log de warning.

### G4.3 — Triggers sem warehouse/factory evaluation

**Arquivo:** `backend/src/simulation/engine.py:158-216`

`_evaluate_triggers` avalia stores e trucks, mas **nao avalia warehouses nem factories**. CLAUDE.md sec 4.4 especifica trigger preditivo para loja/armazem/fabrica.

**Fix:** Adicionar blocos de avaliacao para warehouses e factories no `_evaluate_triggers`.

---

## G5 — Physics & Domain Model Issues

### G5.1 — Caminhao vazio sofre degradacao

**Arquivo:** `backend/src/world/physics.py:20-23`

```python
def calculate_degradation_delta(distance_km, cargo_tons, capacity_tons):
    if distance_km == 0 or capacity_tons == 0:
        return 0.0
    return (distance_km / 1000) * (0.01 + 0.04 * (cargo_tons / capacity_tons))
```

Com `cargo_tons=0`, retorna `(d/1000) * 0.01` — caminhao vazio degrada. CLAUDE.md diz "proporcional a distancia e ao peso transportado".

**Fix:** Adicionar guard: `if cargo_tons == 0: return 0.0`.

### G5.2 — `world/entities/__init__.py` vazio

**Arquivo:** `backend/src/world/entities/__init__.py`

Nao re-exporta as classes. Convencao do projeto (ver `enums/__init__.py`) e re-exportar.

**Fix:** Adicionar imports e `__all__`.

---

## G6 — WebSocket & Publisher Integration

### G6.1 — WebSocket swallows exceptions silently

**Arquivo:** `backend/src/api/websocket.py:88`

```python
except Exception:
    pass
```

Qualquer erro no websocket endpoint e engolido sem log. Impossivel debugar problemas de conexao.

**Fix:** Adicionar `logger.debug(...)` antes do `pass`, ou ao menos logar no `finally`.

### G6.2 — `act_node` chama `publisher.publish_decision()` que nao existe no publisher module

**Arquivos:** `agents/base.py:174,204` vs `simulation/publisher.py`

O publisher module tem `publish_agent_decision(decision, tick, redis_client)` mas o act_node chama `publisher.publish_decision(entity_id, entity_type, raw)` — assinaturas incompativeis.

**Fix:** Alinhar a chamada no act_node com a funcao real `publish_agent_decision`. O Publisher protocol e o adapter devem mapear corretamente.

---

## G7 — Cleanup & Consistency

### G7.1 — `ChaosService.inject_autonomous_event()` duplica logica do `can_inject_autonomous_event()`

**Arquivo:** `backend/src/services/chaos.py:26-62`

As mesmas verificacoes (active_count > 0, cooldown) aparecem em ambos os metodos.

**Fix:** `inject_autonomous_event()` deve chamar `can_inject_autonomous_event()` internamente.

### G7.2 — `OrderService.mark_delivered()` nao trata `target_type="store"`

**Arquivo:** `backend/src/services/order.py:29-36`

Trata `"warehouse"` e `"factory"` mas ignora `"store"`. Se um order e entregue a uma store, o release de stock nao acontece.

**Fix:** Adicionar branch para `"store"` ou ao menos um `else: raise ValueError(...)` para tornar o gap explicito.

### G7.3 — Inconsistencia de naming nos enums de facility status

Factory usa `STOPPED`, Warehouse usa `OFFLINE`, Store usa `OPEN`. Semanticas equivalentes com nomes diferentes.

**Decisao:** Manter como esta — os status refletem dominios diferentes (fabrica "para", armazem "offline", loja "aberta"). A inconsistencia e aceitavel aqui porque cada entidade tem lifecycle distinto. Documentar essa decisao apenas.

---

## Fora de escopo

- **Testes:** Esta feature foca exclusivamente em correcoes de codigo. Novos testes serao adicionados em feature separada.
- **Frontend:** Nenhuma alteracao no frontend.
- **Database schema/migrations:** Nenhuma alteracao de schema. Issues de indexes e cascade serao feature separada.
- **Servicos stub completos:** `simulation.py`, `world_state.py`, `trigger_evaluation.py`, `route.py`, `physics.py` — implementacao minima funcional, nao feature-complete.
