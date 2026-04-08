# Feature 12 — Services: Chaos

## Objetivo

Implementar o `ChaosService` — a camada de negócio responsável por injetar, listar e resolver eventos de caos no mundo simulado. Este service é o único ponto de entrada para mutações na tabela `events`, tanto para eventos manuais (usuário via dashboard) quanto autônomos (MasterAgent). A implementação deve respeitar as regras de concorrência da seção 10.3 do design.md (injeção atômica via `SELECT FOR UPDATE`) para garantir que no máximo 1 evento autônomo fique ativo por vez.

Este service é consumido pela API REST (feature 13), pelo `MasterAgent` (feature 09) e pelo engine (feature 07).

---

## Critérios de Aceitação

### Backend

- [ ] `ChaosService` implementado em `backend/src/services/chaos.py` com todos os métodos definidos em `design.md §6 — ChaosService`
- [ ] `list_active_events()` retorna apenas eventos com `status == "active"` via `EventRepository`
- [ ] `inject_event(data)` cria evento com `source = "user"`, `status = "active"`, `tick_start` preenchido — sem verificação de cooldown (eventos manuais não têm restrição)
- [ ] `inject_autonomous_event(data)` implementa check+insert atômico dentro de uma única transação com `SELECT FOR UPDATE` na tabela `events`:
  - Retorna `None` se já existe evento com `status == "active"`
  - Retorna `None` se `current_tick - last_resolved_autonomous_tick < 24` (cooldown)
  - Insere evento com `source = "master_agent"` somente se ambas as condições passarem
  - **Não** chama `can_inject_autonomous_event()` internamente — a verificação é inline no lock
- [ ] `can_inject_autonomous_event()` é somente-leitura (sem lock) — retorna `bool` para exibição no dashboard; **não** é usada como guarda antes de `inject_autonomous_event()`
- [ ] `resolve_event(event_id)` muda `status` para `"resolved"` e preenche `tick_end` com o tick atual; levanta exceção se evento não existe ou já está resolvido
- [ ] `ChaosService` recebe `EventRepository` e `AsyncSession` via injeção de dependência (FastAPI Depends)
- [ ] O service precisa receber o `current_tick` como parâmetro ou via `SimulationService.get_status()` para preencher `tick_start`, `tick_end` e calcular cooldown

### Testes

- [ ] Testes unitários em `backend/tests/unit/services/test_chaos.py` com `AsyncSession` mockada
- [ ] Teste: `list_active_events` delega para `EventRepository.list_active()`
- [ ] Teste: `inject_event` cria evento com `source="user"` e `status="active"`
- [ ] Teste: `inject_autonomous_event` retorna `None` quando já existe evento ativo
- [ ] Teste: `inject_autonomous_event` retorna `None` quando cooldown não passou (< 24 ticks)
- [ ] Teste: `inject_autonomous_event` cria evento quando não há evento ativo e cooldown passou
- [ ] Teste: `resolve_event` muda status para `"resolved"` e preenche `tick_end`
- [ ] Teste: `resolve_event` levanta exceção para evento inexistente ou já resolvido
- [ ] Teste: `can_inject_autonomous_event` retorna `True`/`False` corretamente sem lock

---

## Fora do Escopo

- Endpoints REST para caos — feature 13 (`api_rest`)
- WebSocket streaming de eventos de caos — feature 14 (`api_websocket`)
- Lógica do `MasterAgent` que decide **quando** acionar caos autônomo — feature 09 (`agents`)
- Efeitos dos eventos de caos nas entidades (reduzir capacidade, bloquear rota) — responsabilidade do engine (feature 07) e dos agentes
- Pub/Sub Redis para canal `nexus:events` — feature 14
