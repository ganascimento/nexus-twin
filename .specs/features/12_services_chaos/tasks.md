# Tasks — Feature 12: Services Chaos

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — estrutura de pastas (§3), convenções (§8), TDD (§9), decisões arquiteturais (§4.4)
- `.specs/features/12_services_chaos/specs.md` — critérios de aceitação
- `.specs/design.md` §6 (`ChaosService`) — assinaturas de métodos
- `.specs/design.md` §10.3 — injeção atômica de caos com `SELECT FOR UPDATE`
- `.specs/design.md` §7 (`EventRepository`) — métodos disponíveis no repositório
- `backend/src/repositories/event.py` — implementação atual do `EventRepository`
- `backend/src/database/models/event.py` — modelo ORM `ChaosEvent`
- `backend/src/enums/events.py` — enums `ChaosEventSource`, `ChaosEventStatus`
- `backend/src/services/factory.py` ou `backend/src/services/warehouse.py` — referência de padrão para services existentes

---

## Plano de Execução

Feature com TDD obrigatório. Execução sequencial em 2 grupos:

1. **Grupo 1** — Escrever todos os testes unitários (fase TDD). Parar e aguardar aprovação.
2. **Grupo 2** — Implementar o `ChaosService` (só após aprovação dos testes).

Não há paralelismo — o service é um único arquivo com dependência direta nos testes.

---

### Grupo 1 — Testes Unitários (TDD — Fase 1)

**Tarefa:** Criar os testes unitários do `ChaosService` com mocks do `EventRepository` e `AsyncSession`.

1. Criar `backend/tests/unit/services/__init__.py` (se não existir)
2. Criar `backend/tests/unit/services/test_chaos.py` com os seguintes testes:

   **Setup comum:**
   - Mock de `EventRepository` com todos os métodos usados pelo service
   - Mock de `AsyncSession` (para transação do `inject_autonomous_event`)
   - Instância de `ChaosService` com os mocks injetados
   - Helper para criar objetos `ChaosEvent` de teste (usando o modelo ORM ou dataclass)

   **Testes:**
   - `test_list_active_events_delegates_to_repository` — chama `list_active_events()`, verifica que `EventRepository.list_active()` foi chamado e o retorno é repassado
   - `test_inject_event_creates_with_source_user` — chama `inject_event(data)`, verifica que o evento criado tem `source="user"`, `status="active"`, `tick_start` preenchido
   - `test_inject_autonomous_event_returns_none_when_active_event_exists` — configura mock para retornar `count_active > 0`, verifica retorno `None`
   - `test_inject_autonomous_event_returns_none_when_cooldown_not_passed` — configura mock para retornar `count_active = 0` e `last_resolved_tick` dentro do cooldown (< 24 ticks), verifica retorno `None`
   - `test_inject_autonomous_event_creates_when_conditions_met` — configura mock para retornar `count_active = 0` e cooldown expirado, verifica que evento é criado com `source="master_agent"`
   - `test_resolve_event_updates_status_and_tick_end` — chama `resolve_event(event_id)`, verifica que status muda para `"resolved"` e `tick_end` é preenchido
   - `test_resolve_event_raises_for_nonexistent_event` — configura mock para retornar `None`, verifica que levanta exceção
   - `test_resolve_event_raises_for_already_resolved_event` — configura mock para retornar evento com `status="resolved"`, verifica que levanta exceção
   - `test_can_inject_autonomous_event_returns_true_when_allowed` — sem evento ativo e cooldown expirado
   - `test_can_inject_autonomous_event_returns_false_when_active_event` — evento ativo existe
   - `test_can_inject_autonomous_event_returns_false_when_cooldown_active` — cooldown não passou

3. Verificar que os testes falham por falta de implementação (importação do `ChaosService` vai falhar — isso é esperado)

**⚠ Parar aqui. Não implementar código de produção. Aguardar aprovação do usuário.**

---

### Grupo 2 — Implementação do ChaosService

**Tarefa:** Implementar `ChaosService` em `backend/src/services/chaos.py` seguindo as assinaturas de `design.md §6` e os mecanismos de concorrência de `design.md §10.3`.

1. Implementar `ChaosService` em `backend/src/services/chaos.py`:
   - Constructor recebe `EventRepository` e `AsyncSession`
   - `list_active_events()` → delega para `EventRepository.list_active()`
   - `inject_event(data, current_tick)` → cria evento via repository com `source="user"`, `status="active"`, `tick_start=current_tick`
   - `inject_autonomous_event(data, current_tick)` → implementa padrão `SELECT FOR UPDATE` da seção 10.3:
     - Abre transação
     - `SELECT count(*) FROM events WHERE status='active' FOR UPDATE`
     - Se `count > 0` → retorna `None`
     - Busca `last_resolved_autonomous_tick` via repository
     - Se `current_tick - last_tick < 24` → retorna `None`
     - Cria evento com `source="master_agent"`
   - `resolve_event(event_id, current_tick)` → busca evento, valida que existe e está ativo, muda `status="resolved"`, preenche `tick_end=current_tick`
   - `can_inject_autonomous_event(current_tick)` → somente-leitura, sem lock — verifica `count_active == 0` e cooldown via queries normais

2. Atualizar `backend/src/services/__init__.py` se necessário para exportar `ChaosService`

3. Rodar `pytest backend/tests/unit/services/test_chaos.py -v` — todos os testes devem passar

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes passam com `pytest`.
Atualizar `state.md`: setar o status da feature `12` para `done`.
