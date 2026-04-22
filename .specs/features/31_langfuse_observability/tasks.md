# Tasks — Feature 31: Langfuse Observability

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — TDD (§9), convenções (§8), estrutura de pastas (§3), variáveis de ambiente (§6), dependências (§5)
- `.specs/features/31_langfuse_observability/specs.md` — critérios de aceitação
- `.specs/design.md §12` — **Observability — Langfuse** (infra Docker, integração com agentes, metadata, graceful degradation, env vars)
- `.specs/prd.md §9.1` — Observabilidade dos Agentes (motivação do produto)
- `backend/src/agents/base.py` — `build_agent_graph`, `_make_decide_node`, `_act_node`, `_make_perceive_node` (onde o callback entra)
- `backend/src/agents/store_agent.py`, `warehouse_agent.py`, `factory_agent.py`, `truck_agent.py` — `run_cycle` em cada um (onde `graph.ainvoke(...)` é chamado e precisa receber `config={...}`)
- `backend/src/simulation/events.py` — `SimulationEvent` (campos usados por `build_trace_metadata` e `extract_session_id`)
- `docker-compose.yml` — estrutura atual dos serviços (adicionar os 6 serviços Langfuse sem quebrar os existentes)
- `backend/.env.example` e `backend/.env` — padrão de variáveis existentes
- `backend/tests/unit/agents/test_base.py` — padrão de teste com mocking de `ChatOpenAI` via `patch("src.agents.base.ChatOpenAI", ...)`
- `backend/tests/integration/simulation/conftest.py` — autouse fixture que substitui `ChatOpenAI` por `_NoOpenAIStub` (testes de integração não devem acionar Langfuse real)

**Pré-requisito:** features `01_project_setup`, `08_agent_base`, `09_agents`, `24_decision_effect_processor` em status `done`. A instrumentação é aditiva e não altera semântica dos agentes.

**TDD aplica:** Sim. A maior parte da lógica nova é testável em isolamento: inicialização condicional do handler, extração de metadata/session do trigger, injeção/ausência do callback no `build_agent_graph`. Grupo 1 é a fase de testes — parar e aguardar aprovação antes da implementação.

---

## Plano de Execução

1. **Grupo 1** — Fase 1 (TDD): escrever todos os testes novos. **Parar e aguardar aprovação.**
2. **Grupos 2 e 3 em paralelo** (após aprovação dos testes):
   - Grupo 2 — módulo `observability/langfuse.py` + `__init__.py`
   - Grupo 3 — infra Docker Compose + `.env.example` + `pyproject.toml`
3. **Grupo 4** (sequencial, depende do Grupo 2) — integração em `agents/base.py` (callback no `ChatOpenAI`, tagging em `_act_node` e fast_path)
4. **Grupo 5** (sequencial, depende do Grupo 4) — cada um dos 4 agents passa `config` no `graph.ainvoke`
5. **Grupo 6** (sequencial, depende de 2–5) — documentação no README + atualização do `state.md`
6. **Grupo 7** (validação, último) — rodar testes + subida do docker-compose + smoke test manual do dashboard

---

### Grupo 1 — Fase 1 (TDD): Testes (um agente)

**Tarefa:** Escrever todos os testes novos necessários para a feature. **Não implementar código de produção neste grupo.**

1. Criar `backend/tests/unit/observability/__init__.py` (arquivo vazio).

2. Criar `backend/tests/unit/observability/test_langfuse.py` com os seguintes testes:
   - `test_get_callback_handler_returns_none_when_public_key_missing` — usa `monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)` e `monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")`; importa `get_callback_handler` e confirma que retorna `None`.
   - `test_get_callback_handler_returns_none_when_secret_key_missing` — simétrico ao anterior.
   - `test_get_callback_handler_returns_none_when_both_empty_strings` — `LANGFUSE_PUBLIC_KEY=""` e `LANGFUSE_SECRET_KEY=""`; retorna `None`.
   - `test_get_callback_handler_returns_handler_when_both_keys_set` — `setenv` ambas as keys; importa e confirma que o retorno tem atributo compatível com `CallbackHandler` (usar `isinstance` se possível, senão `hasattr` em métodos do handler) OR patch `CallbackHandler` de `langfuse.callback` com `MagicMock` e confirmar que foi instanciado.
   - `test_get_callback_handler_defaults_host_to_localhost` — só as keys setadas, `LANGFUSE_HOST` ausente; confirma via spy que o construtor do `CallbackHandler` recebeu `host="http://localhost:3100"`.
   - `test_build_trace_metadata_extracts_all_fields` — cria `SimulationEvent(event_type="low_stock_trigger", source="engine", entity_type="store", entity_id="store-001", payload={"order_id": "abc-123"}, tick=42)`, chama `build_trace_metadata(event)` e assert `{"agent_type": "store", "entity_id": "store-001", "trigger_event": "low_stock_trigger", "trigger_payload": {"order_id": "abc-123"}, "tick": 42}`.
   - `test_extract_session_id_returns_order_id_when_present` — payload com `order_id="abc-123"`; retorna `"abc-123"`.
   - `test_extract_session_id_returns_none_when_payload_empty` — payload `{}`; retorna `None`.
   - `test_extract_session_id_returns_none_when_payload_missing_order_id` — payload `{"material_id": "cimento"}`; retorna `None`.
   - `test_extract_session_id_returns_none_when_order_id_is_none_or_empty` — payload `{"order_id": None}` e `{"order_id": ""}`; ambos retornam `None`.
   - `test_extract_session_id_coerces_non_string_order_id` — payload `{"order_id": 42}` retorna `"42"`.

   Importante: como o módulo `src/observability/langfuse.py` ainda não existe nesta fase, os imports vão falhar. Adicionar `pytest.importorskip("src.observability.langfuse")` no topo **não** é a solução — o objetivo é que os testes falhem agora e passem após o Grupo 2. Usar import direto e deixar falhar com `ImportError`/`AttributeError` — é o comportamento esperado do TDD.

3. Acrescentar em `backend/tests/unit/agents/test_base.py`:
   - `test_build_agent_graph_without_langfuse_handler_has_no_callbacks` — patch `src.agents.base.get_callback_handler` retornando `None`; patch `src.agents.base.ChatOpenAI` com `MagicMock` (spy); chama `build_agent_graph(agent_type="store", tools=[], decision_schema_map={}, db_session=MagicMock(), publisher_instance=AsyncMock())`; assert que o `ChatOpenAI` foi chamado **sem** `callbacks` nas kwargs, ou com `callbacks=[]`.
   - `test_build_agent_graph_with_langfuse_handler_injects_callback` — patch `get_callback_handler` retornando um `MagicMock()` (handler simulado); patch `ChatOpenAI` como spy; chama `build_agent_graph`; assert que `ChatOpenAI` recebeu `callbacks` contendo o handler mock.
   - `test_act_node_tags_trace_error_on_validation_failure` — patch `get_callback_handler` retornando um `MagicMock` (com método `update_current_trace`); força Pydantic a falhar (schema_map lança `ValueError` no init); confirma que `handler.update_current_trace.assert_called_once()` foi chamado com `level="ERROR"` e alguma `status_message` não vazia.
   - `test_act_node_does_not_call_trace_update_when_handler_is_none` — patch `get_callback_handler` retornando `None`; força validação a falhar; confirma que não há `AttributeError` (guard funciona) e que nenhum método de handler foi chamado.
   - `test_fast_path_decision_tags_metadata_fast_path_taken` — patch handler como `MagicMock`; monta state com `fast_path_taken=True` e decisão "hold"; confirma que `handler.update_current_trace` foi chamado com `metadata={"fast_path_taken": True}` (ou kwarg equivalente).

**Parar aqui. Não implementar código de produção. Aguardar aprovação do usuário.**

---

### Grupo 2 — Módulo Observability (um agente, após aprovação dos testes)

**Tarefa:** Criar o módulo `src/observability/` com o handler Langfuse e os helpers de metadata.

1. Criar `backend/src/observability/__init__.py`:
   - Re-export: `from src.observability.langfuse import get_callback_handler, build_trace_metadata, extract_session_id`

2. Criar `backend/src/observability/langfuse.py`:
   - Imports: `os`, `from typing import Optional`, `from langfuse.callback import CallbackHandler` (nome do módulo pode variar entre versões do `langfuse`; ajustar conforme 3.x).
   - Variável module-level `_cached_handler: CallbackHandler | None = None` e `_initialized: bool = False`.
   - Função `get_callback_handler() -> CallbackHandler | None`:
     - Se `_initialized` é True, retorna `_cached_handler` direto (cache).
     - Lê `os.environ.get("LANGFUSE_PUBLIC_KEY", "")` e `os.environ.get("LANGFUSE_SECRET_KEY", "")`.
     - Se qualquer das duas for vazia/None, seta `_initialized=True`, `_cached_handler=None`, retorna `None`.
     - Senão, instancia `CallbackHandler(public_key=..., secret_key=..., host=os.environ.get("LANGFUSE_HOST", "http://localhost:3100"))`, seta cache, retorna.
     - Try/except ao redor do `CallbackHandler(...)` — se levantar (ex: langfuse indisponível), loga warning com Loguru e retorna `None`; não propaga.
   - Função `build_trace_metadata(trigger) -> dict`:
     - Retorna `{"agent_type": trigger.entity_type, "entity_id": trigger.entity_id, "trigger_event": trigger.event_type, "trigger_payload": trigger.payload or {}, "tick": trigger.tick}`.
   - Função `extract_session_id(trigger) -> str | None`:
     - `payload = trigger.payload or {}`
     - `order_id = payload.get("order_id")`
     - `if not order_id: return None`
     - `return str(order_id)`

3. Rodar `python -c "from src.observability import get_callback_handler, build_trace_metadata, extract_session_id; print('ok')"` a partir de `backend/` para confirmar que os imports funcionam.

4. Rodar `pytest backend/tests/unit/observability/test_langfuse.py -v` e confirmar que os 11 testes passam.

---

### Grupo 3 — Infraestrutura: Docker Compose + pyproject + env (um agente, em paralelo ao Grupo 2)

**Tarefa:** Montar a stack Langfuse no Docker Compose, adicionar a dependência Python e atualizar o `.env.example`.

1. Adicionar em `backend/pyproject.toml` na seção `[project.dependencies]`:
   - `langfuse>=3.0,<4`
   - Rodar `pip install -e .` em `backend/` com o venv ativado para instalar.

2. Editar `docker-compose.yml` — adicionar após o bloco do `valhalla` (não modificar os serviços existentes):
   - `langfuse-postgres`: imagem `postgres:15-alpine`, env `POSTGRES_USER=langfuse`, `POSTGRES_PASSWORD=langfuse`, `POSTGRES_DB=langfuse`, volume `langfuse_pgdata:/var/lib/postgresql/data`, healthcheck `pg_isready -U langfuse`.
   - `langfuse-clickhouse`: imagem `clickhouse/clickhouse-server:24.3-alpine`, env `CLICKHOUSE_USER=langfuse`, `CLICKHOUSE_PASSWORD=langfuse`, `CLICKHOUSE_DB=default`, volume `langfuse_clickhouse:/var/lib/clickhouse`, healthcheck comentado (começo complexo — deixar para o depends_on com `service_started`).
   - `langfuse-redis`: imagem `redis:7-alpine`, volume opcional, healthcheck `redis-cli ping`. Command: `redis-server --requirepass langfuse`.
   - `langfuse-minio`: imagem `minio/minio`, command `server /data --console-address ":9001"`, env `MINIO_ROOT_USER=langfuse`, `MINIO_ROOT_PASSWORD=langfuse1234`, volume `langfuse_minio:/data`.
   - `langfuse-worker`: imagem `langfuse/langfuse-worker:3`, `depends_on` dos 4 anteriores, env vars:
     - `DATABASE_URL=postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse`
     - `CLICKHOUSE_URL=http://langfuse-clickhouse:8123`
     - `CLICKHOUSE_USER=langfuse`, `CLICKHOUSE_PASSWORD=langfuse`, `CLICKHOUSE_MIGRATION_URL=clickhouse://langfuse-clickhouse:9000`
     - `REDIS_HOST=langfuse-redis`, `REDIS_PORT=6379`, `REDIS_AUTH=langfuse`
     - `LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse`, `LANGFUSE_S3_EVENT_UPLOAD_REGION=auto`, `LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=langfuse`, `LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=langfuse1234`, `LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://langfuse-minio:9000`, `LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true`
     - `NEXTAUTH_SECRET=mysecret-change-in-prod`, `SALT=mysalt-change-in-prod`, `ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000` (64 hex; documentar geração com `openssl rand -hex 32`)
     - `TELEMETRY_ENABLED=false`, `LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=false`
   - `langfuse-web`: imagem `langfuse/langfuse:3`, `depends_on` `langfuse-worker`, porta `3100:3000`, mesmas env vars do worker mais:
     - `NEXTAUTH_URL=http://localhost:3100`
     - `LANGFUSE_INIT_ORG_ID=nexus-twin-org`, `LANGFUSE_INIT_ORG_NAME=NexusTwin`
     - `LANGFUSE_INIT_PROJECT_ID=nexus-twin`, `LANGFUSE_INIT_PROJECT_NAME=NexusTwin`
   - Declarar os 3 volumes novos no bloco `volumes:` do topo: `langfuse_pgdata`, `langfuse_clickhouse`, `langfuse_minio`.

3. Editar `backend/.env.example` — adicionar após a seção de Valhalla:
   ```dotenv
   # Observability (Langfuse) — opcional
   # Vazias desativam a instrumentação; projeto roda normalmente.
   # Ao subir o Langfuse local pela primeira vez, acesse http://localhost:3100,
   # crie um user, abra o projeto "NexusTwin", vá em Settings > API Keys,
   # e cole public_key e secret_key aqui.
   LANGFUSE_PUBLIC_KEY=
   LANGFUSE_SECRET_KEY=
   LANGFUSE_HOST=http://localhost:3100
   ```

4. Rodar `docker compose config` e confirmar que o YAML é válido (sem erros de parsing).

---

### Grupo 4 — Integração em `agents/base.py` (um agente, depende do Grupo 2)

**Tarefa:** Plugar o handler no `build_agent_graph`, taggear falhas no `_act_node` e marcar fast-path no metadata.

1. Editar `backend/src/agents/base.py`:
   - Import no topo: `from src.observability.langfuse import get_callback_handler`.
   - Em `build_agent_graph`, antes de `llm = ChatOpenAI(...)`:
     - `handler = get_callback_handler()`
     - `llm_kwargs = {"model": OPENAI_MODEL, "max_retries": OPENAI_MAX_RETRIES, "timeout": OPENAI_TIMEOUT_SECONDS}`
     - `if handler is not None: llm_kwargs["callbacks"] = [handler]`
     - `llm = ChatOpenAI(**llm_kwargs)`
   - Em `_make_act_node_for_graph`, dentro do `except Exception as e:` do `_act_node`, antes do `logger.exception(...)`:
     - `handler = get_callback_handler()`
     - `if handler is not None and hasattr(handler, "update_current_trace"):`
       - `try: handler.update_current_trace(level="ERROR", status_message=str(e)[:500])`
       - `except Exception: pass` — não propagar falha de tagging
   - Em `_make_act_node_for_graph`, no caminho de sucesso quando `state.get("fast_path_taken") is True`:
     - `handler = get_callback_handler()`
     - `if handler is not None and hasattr(handler, "update_current_trace"):`
       - `try: handler.update_current_trace(metadata={"fast_path_taken": True})`
       - `except Exception: pass`

2. Rodar `pytest backend/tests/unit/agents/test_base.py -v` e confirmar que todos os testes passam, inclusive os novos adicionados no Grupo 1.

---

### Grupo 5 — Propagar `config` nos 4 agents (um agente, depende do Grupo 4)

**Tarefa:** Em cada `run_cycle`, passar `config={"callbacks": ..., "metadata": ..., "run_name": ..., "tags": ...}` no `graph.ainvoke`.

Editar os 4 arquivos (mesmo padrão em cada):
- `backend/src/agents/store_agent.py`
- `backend/src/agents/warehouse_agent.py`
- `backend/src/agents/factory_agent.py`
- `backend/src/agents/truck_agent.py`

Em cada `run_cycle`:

1. Imports no topo: `from src.observability.langfuse import get_callback_handler, build_trace_metadata, extract_session_id`.

2. Antes do `await graph.ainvoke(initial_state)`:
   ```python
   handler = get_callback_handler()
   metadata = build_trace_metadata(trigger)
   session_id = extract_session_id(trigger)
   if session_id is not None:
       metadata["langfuse_session_id"] = session_id
   config = {
       "callbacks": [handler] if handler is not None else [],
       "metadata": metadata,
       "run_name": f"{metadata['agent_type']}:{metadata['entity_id']}:{metadata['trigger_event']}",
       "tags": [
           f"agent:{metadata['agent_type']}",
           f"event:{metadata['trigger_event']}",
       ],
   }
   ```

3. Trocar `await graph.ainvoke(initial_state)` por `await graph.ainvoke(initial_state, config=config)`.

4. Rodar `pytest backend/tests/unit/agents/ -v` e confirmar que todos passam.

---

### Grupo 6 — Documentação (um agente, depende dos Grupos 2–5)

**Tarefa:** Atualizar o `README.md` da raiz e o `state.md`.

1. Editar `README.md` — adicionar seção **Observability (optional)** logo após a seção `## Run the application` / antes de `## Geo Data Setup`. Conteúdo:

   ```markdown
   ## Observability (optional)

   Nexus Twin ships with optional integration to [Langfuse](https://langfuse.com) (self-hosted) to give you tracing and metrics for every agent decision: prompt + response + tokens + cost + latency per LLM call, grouped by agent, entity, trigger event and order.

   Without the Langfuse env vars set, the system runs exactly as before — zero overhead.

   ### Bring up the Langfuse stack

   The `docker-compose.yml` already includes the Langfuse services (`langfuse-web`, `langfuse-worker`, and their dependencies). Running `docker compose up -d` brings everything up together. To start only the observability stack:

   \`\`\`bash
   docker compose up -d langfuse-web langfuse-worker langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio
   \`\`\`

   Wait ~30-60s for ClickHouse migrations to finish and the web UI to become available.

   ### Create your keys

   1. Open `http://localhost:3100` in the browser
   2. Sign up (first user becomes admin of the local instance)
   3. Open the `NexusTwin` project
   4. Go to **Settings → API Keys** and create a new keypair
   5. Copy `public_key` and `secret_key` into `backend/.env`:

   \`\`\`dotenv
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=http://localhost:3100
   \`\`\`

   6. Restart the backend — every agent decision now shows up in the Langfuse dashboard

   ### Disable

   Leave `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` blank (or remove them) and restart the backend. Nothing will be sent anywhere.
   ```

   (Substituir os blocos de código escapados `\`\`\`` pelos crases reais.)

2. Adicionar `langfuse-web` ao quadro **Service Ports** do README:
   | Langfuse dashboard | 3100 | Optional observability UI |

3. Editar `.specs/state.md`:
   - Trocar o status da linha feature 31 de `pending` para `done`.
   - Adicionar nas **Implementation Decisions** uma entrada por decisão relevante que surgir durante a implementação (ex: nome da função do handler, caminho de módulo, decisão sobre cache module-level, etc.).

---

### Grupo 7 — Validação (sequencial, último)

**Tarefa:** Rodar todos os testes e validar end-to-end que a stack sobe.

1. Rodar `pytest backend/tests/unit -q` — todos passam (era 616 antes; vira pelo menos 616 + N novos).

2. Rodar `pytest backend/tests/integration -q --timeout=240` — todos passam (era 204); a autouse fixture que substitui `ChatOpenAI` por `_NoOpenAIStub` garante que nenhum teste de integração tenta chamar Langfuse real.

3. Rodar `docker compose up -d langfuse-web langfuse-worker langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio`. Esperar 60s.

4. Rodar `curl -s -o /dev/null -w "%{http_code}" http://localhost:3100` — retorna `200` ou `307` (redirect pra signup).

5. Validação manual rápida:
   - Acessar `http://localhost:3100`, criar user, abrir o projeto `NexusTwin`, pegar `public_key`/`secret_key`
   - Colocar em `backend/.env`
   - Subir o backend, rodar 1-2 ticks com a simulação (OpenAI key válida)
   - Voltar ao dashboard do Langfuse: em **Traces**, deve aparecer pelo menos um trace com `run_name = store:store-XXX:low_stock_trigger` (ou similar) com tokens, custo, latência preenchidos

6. Confirmar que remover as keys do `.env`, reiniciar o backend e rodar ticks **não** causa erro — sistema volta ao modo sem instrumentação.

Se qualquer passo falhar, corrigir antes de marcar a feature como `done`.

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos e toda a validação do Grupo 7 passa sem erros.
Atualizar `.specs/state.md`: setar o status da feature `31` para `done`.
