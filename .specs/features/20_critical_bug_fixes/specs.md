# Feature 20 — Critical Bug Fixes

> Auditoria completa do codebase identificou 11 bugs criticos que impedem a aplicacao de funcionar.
> Bugs divididos em dois grupos: crashes imediatos (aplicacao nao sobe ou endpoints falham) e resultados silenciosamente errados (aplicacao roda mas produz lixo).

---

## Escopo

Correcoes focadas exclusivamente em bugs que **quebram o funcionamento** da aplicacao. Melhorias de qualidade, performance e validacao estao fora de escopo.

---

## C1 — Crashes na construcao do WorldState

### C1.1 — `Truck.name` nao existe no modelo de banco

**Arquivo:** `backend/src/services/world_state.py:172`

```python
TruckEntity(
    id=t.id,
    name=t.name,  # AttributeError — coluna nao existe no modelo Truck
    ...
)
```

O modelo SQLAlchemy `Truck` (`database/models/truck.py`) nao tem coluna `name`. A entidade Pydantic `TruckEntity` (`world/entities/truck.py`) tambem nao tem campo `name`. Crash no primeiro `load()`.

**Fix:** Remover `name=t.name`.

### C1.2 — `base_lat`/`base_lng` faltando na construcao do TruckEntity

**Arquivo:** `backend/src/services/world_state.py:170-184`

`TruckEntity` define `base_lat: float` e `base_lng: float` como campos obrigatorios. O codigo passava `current_lat`/`current_lng` mas omitia `base_lat`/`base_lng`. Pydantic `ValidationError` em todo `load()`.

**Fix:** Adicionar `base_lat=t.base_lat, base_lng=t.base_lng`.

### C1.3 — `Store.region` nao existe no modelo de banco

**Arquivo:** `backend/src/services/world_state.py:159`

```python
StoreEntity(
    ...
    region=s.region,  # AttributeError — Store nao tem coluna region
    ...
)
```

Modelo `Store` (`database/models/store.py`) nao tem coluna `region`. `StoreEntity` (`world/entities/store.py`) tambem nao tem campo `region`. Somente `Warehouse` tem `region`. Seed data de stores nao inclui `region`.

**Fix:** Remover `region=s.region`.

---

## C2 — API endpoints quebrados

### C2.1 — `get_snapshot()` — metodo inexistente no WorldStateService

**Arquivo:** `backend/src/api/routes/world.py:10`

```python
return await service.get_snapshot()  # AttributeError — metodo e load()
```

O `WorldStateService` define `load()`, nao `get_snapshot()`. Endpoint `GET /api/v1/world/snapshot` crash com `AttributeError`.

**Fix:** Alterar para `service.load()`.

### C2.2 — `simulation_service` nunca inicializado no lifespan

**Arquivos:** `backend/src/main.py` (lifespan) + `backend/src/api/dependencies.py:70-71`

```python
async def get_simulation_service(request: Request):
    return request.app.state.simulation_service  # AttributeError — nunca setado
```

O lifespan inicializa Redis e WebSocket mas **nao cria** o `SimulationEngine` nem o `SimulationService`. Todos os 5 endpoints de simulacao (`/start`, `/stop`, `/tick`, `/status`, `/speed`) e o endpoint `/world/tick` crasham.

**Fix:** Inicializar `SimulationEngine` + `SimulationService` no lifespan com `WorldStateService`, Redis client e `AsyncSessionLocal` como session factory. Adicionar graceful shutdown no teardown.

### C2.3 — `await` em metodos sincronos do SimulationService

**Arquivos:** `backend/src/api/routes/simulation.py:33,39` + `backend/src/api/routes/world.py:15`

```python
return await service.get_status()        # TypeError — get_status() retorna dict, nao coroutine
await service.set_tick_interval(...)     # TypeError — idem
```

`SimulationService.get_status()` e `set_tick_interval()` sao metodos sync que retornam `dict`. Chamados com `await`, geram `TypeError: object dict can't be used in 'await' expression`.

**Fix:** Remover `await` das chamadas a metodos sync.

---

## C3 — Agent system quebrado

### C3.1 — ChaosService instanciado sem `__init__`

**Arquivo:** `backend/src/agents/master_agent.py:61`

```python
chaos_service = ChaosService.__new__(ChaosService)  # pula __init__
can_inject = await chaos_service.can_inject_autonomous_event(tick)  # self._repo nao existe
```

`__new__()` cria o objeto sem chamar `__init__()`. `self._repo` e `self._session` nunca sao atribuidos. Primeira chamada a qualquer metodo gera `AttributeError`.

**Fix:** Criar sessao via `AsyncSessionLocal`, instanciar `EventRepository` e `ChaosService` corretamente. Commit apos injecao de evento.

### C3.2 — Placeholders de prompt nunca substituidos

**Arquivo:** `backend/src/agents/base.py:93-98`

```python
prompt = prompt.replace("{entity_id}", state["entity_id"])
prompt = prompt.replace("{trigger_event}", state["trigger_event"])
# {world_state_summary}, {decision_history}, {truck_type} — nunca substituidos
```

Todos os prompts (factory.md, warehouse.md, store.md, truck.md) contem `{world_state_summary}`, `{decision_history}` e truck.md contem `{truck_type}`. Esses placeholders sao enviados como texto literal ao LLM. Agentes tomam decisoes sem contexto real — output e lixo.

**Fix:** Adicionar funcoes `_format_world_state_summary()` e `_format_decision_history()` que serializam os dados em texto. Substituir `{truck_type}` para agentes truck.

### C3.3 — `AgentDecision.create()` com campos errados

**Arquivo:** `backend/src/agents/base.py:229-236`

```python
await repo.create({
    "entity_id": state["entity_id"],
    "entity_type": entity_type,   # coluna e agent_type, nao entity_type
    "tick": state["current_tick"],
    "action": raw.get("action"),
    "payload": raw.get("payload", {}),
    # event_type faltando — coluna NOT NULL
})
```

O modelo `AgentDecision` (`database/models/agent_decision.py`) tem coluna `agent_type` (nao `entity_type`) e `event_type` (NOT NULL, obrigatorio). O dict passa a key errada e omite um campo obrigatorio. `TypeError` no construtor SQLAlchemy ou `IntegrityError` no flush.

**Fix:** Renomear `entity_type` → `agent_type`, adicionar `event_type` vindo de `state["trigger_event"]`.

### C3.4 — `_format_decision_history` — SQLAlchemy models nao serializaveis

**Arquivo:** `backend/src/agents/base.py` (funcao nova)

`get_recent_by_entity()` retorna `list[AgentDecision]` (modelos SQLAlchemy). `str()` de um modelo SQLAlchemy produz `<AgentDecision ...>` — inutil para o prompt do LLM.

**Fix:** Extrair campos relevantes (`tick`, `action`, `event_type`, `payload`) e serializar como JSON.

---

## C4 — Simulation engine: dados perdidos

### C4.1 — `session.commit()` faltando no `_apply_physics`

**Arquivo:** `backend/src/simulation/engine.py:70-156`

```python
async def _apply_physics(self, world_state: WorldState) -> None:
    async with self._session_factory() as session:
        # ~80 linhas de writes: update_position, update_stock, update_degradation...
        # NENHUM commit
```

`AsyncSession` como context manager chama `close()` no exit — que faz rollback de tudo que nao foi committed. Todas as atualizacoes de physics (posicao de caminhoes, consumo de estoque, degradacao, producao) sao descartadas silenciosamente a cada tick.

**Fix:** Adicionar `await session.commit()` ao final do bloco.

---

## C5 — RouteService: criacao com campos errados

### C5.1 — `create_route()` passa campos incompativeis com o modelo Route

**Arquivo:** `backend/src/services/route.py:42-54`

```python
await self._repo.create({
    "truck_id": truck_id,
    "origin_id": origin_id,           # falta origin_type
    "destination_id": destination_id,  # modelo usa dest_type + dest_id
    "distance_km": ...,               # coluna nao existe
    # started_at faltando — NOT NULL
})
```

O modelo `Route` (`database/models/route.py`) tem: `origin_type`, `origin_id`, `dest_type`, `dest_id`, `started_at` (NOT NULL). O service passa nomes errados e omite campos obrigatorios. `IntegrityError` na criacao de qualquer rota.

**Fix:** Atualizar assinatura e dict para: `origin_type`, `origin_id`, `dest_type`, `dest_id`, `started_at=datetime.now(UTC)`. Remover `distance_km`.

---

## Resumo de impacto

| Grupo | Bugs | Impacto |
|-------|------|---------|
| C1 — WorldState | 3 | App nao carrega estado do mundo |
| C2 — API | 3 | 7 endpoints crasham |
| C3 — Agents | 4 | Agentes nao funcionam |
| C4 — Engine | 1 | Fisica nao persiste |
| C5 — Routes | 1 | Rotas nao sao criadas |
| **Total** | **11** | **Aplicacao inteira inoperante** |
