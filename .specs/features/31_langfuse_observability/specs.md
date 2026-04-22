# Feature 31 — Langfuse Observability

## Objetivo

Plugar [Langfuse](https://langfuse.com) self-hosted no Multi-Agent System para dar **tracing de causalidade** e **métricas por decisão** sem alterar a lógica dos agentes. Cada chamada ao LLM vira um span com prompt + resposta + tokens in/out + custo estimado + latência + versão do modelo; cada ciclo de agente (um `run_cycle`) vira um trace agrupando tudo que aconteceu para aquela decisão com metadata estruturada (`agent_type`, `entity_id`, `trigger_event`, `tick`). Quando a decisão envolve um `order_id`, o trace é marcado com `session_id = order_id` para agrupar no dashboard todo o caminho da ordem (store → warehouse → truck pickup → truck delivery).

Esta feature é **opt-in**: sem `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` no ambiente, o handler fica `None` e o sistema roda exatamente como antes (zero overhead). Com as keys setadas, o dashboard em `http://localhost:3100` mostra traces, custos, latência e permite filtrar por agente/trigger/entidade — entregando os pilares #1 e #4 (tracing de causalidade + métricas) da discussão de observabilidade sem construir painel próprio.

Esta é uma feature de instrumentação — desbloqueia debugging profundo, auditoria de decisões e análise de custo por agente/gatilho, sem bloquear nenhuma feature futura.

---

## Critérios de Aceitação

### Backend

- [ ] `langfuse>=3.0` adicionado em `backend/pyproject.toml` como dependência core (não dev)
- [ ] `backend/src/observability/__init__.py` existe (re-exporta `get_callback_handler`, `build_trace_metadata`, `extract_session_id`)
- [ ] `backend/src/observability/langfuse.py` implementa:
  - [ ] `get_callback_handler() -> CallbackHandler | None` — lê `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` do ambiente; retorna `None` se qualquer uma das duas primeiras estiver vazia ou não setada; cacheia a instância em module-level após a primeira chamada
  - [ ] `build_trace_metadata(trigger)` — retorna `dict` com chaves `agent_type` (derivado de `trigger.entity_type`), `entity_id` (de `trigger.entity_id`), `trigger_event` (de `trigger.event_type`), `trigger_payload` (de `trigger.payload`), `tick` (de `trigger.tick`)
  - [ ] `extract_session_id(trigger) -> str | None` — se `trigger.payload` tem chave `order_id` e o valor é truthy, retorna `str(order_id)`; caso contrário `None`
- [ ] `src/agents/base.py::build_agent_graph` injeta o handler como callback do `ChatOpenAI` apenas quando o handler não é `None`:
  - [ ] `ChatOpenAI(..., callbacks=[handler])` quando disponível
  - [ ] `ChatOpenAI(...)` sem `callbacks` quando handler é `None` (comportamento atual preservado)
- [ ] Cada um dos 4 `run_cycle` (`store_agent.py`, `warehouse_agent.py`, `factory_agent.py`, `truck_agent.py`) passa `config={"callbacks": [...], "metadata": build_trace_metadata(trigger), "run_name": "<agent>:<entity>:<event>", "tags": ["agent:<type>", "event:<type>"]}` no `graph.ainvoke(initial_state, config=...)`. Quando o handler é `None`, `callbacks` vira lista vazia (sem crash)
- [ ] Quando `extract_session_id(trigger)` retorna um valor, ele é passado em `config["metadata"]["langfuse_session_id"] = <order_id>` para o handler do LangChain propagar como session do trace
- [ ] `_act_node` em `src/agents/base.py` marca a trace atual com `level="ERROR"` e `status_message=str(e)` quando a validação Pydantic ou o `extract_json_from_last_message` lançam exceção, via `handler.update_current_trace(level="ERROR", status_message=...)` (guard para handler `None`)
- [ ] Fast-path hold adiciona `metadata={"fast_path_taken": True}` ao trace para que o dashboard mostre claramente quando uma decisão foi tomada sem LLM
- [ ] Variáveis de ambiente adicionadas em `backend/.env.example` (`LANGFUSE_PUBLIC_KEY=`, `LANGFUSE_SECRET_KEY=`, `LANGFUSE_HOST=http://localhost:3100`) com comentário explicando que vazias desativam a instrumentação

### Infraestrutura

- [ ] `docker-compose.yml` ganha 6 serviços Langfuse novos, isolados do `postgres`/`redis` do Nexus Twin:
  - [ ] `langfuse-postgres` — `postgres:15-alpine`, volume próprio `langfuse-pgdata`, db `langfuse`
  - [ ] `langfuse-clickhouse` — `clickhouse/clickhouse-server:24.3-alpine`, volume próprio `langfuse-clickhouse-data`
  - [ ] `langfuse-redis` — `redis:7-alpine` separado do redis principal
  - [ ] `langfuse-minio` — `minio/minio`, volume próprio `langfuse-minio-data`
  - [ ] `langfuse-worker` — `langfuse/langfuse-worker:3`, depende dos 4 de cima
  - [ ] `langfuse-web` — `langfuse/langfuse:3`, expõe porta `3100`, depende do worker
- [ ] `docker compose up -d` sobe a stack inteira (Nexus Twin + Langfuse) sem erro e os healthchecks dos serviços Langfuse passam em até 60s
- [ ] `GET http://localhost:3100` retorna `200` e exibe a página de signup/login do Langfuse
- [ ] Nenhuma das variáveis do Langfuse tem valor secreto real hardcoded no `docker-compose.yml` — credenciais internas usam placeholders documentados apenas para a instância local (ex: `NEXTAUTH_SECRET` com comentário explicando); produção ficaria para depois

### Testes

- [ ] `backend/tests/unit/observability/__init__.py` existe
- [ ] `backend/tests/unit/observability/test_langfuse.py` cobre:
  - [ ] `get_callback_handler` retorna `None` quando `LANGFUSE_PUBLIC_KEY` está vazio/ausente
  - [ ] `get_callback_handler` retorna `None` quando `LANGFUSE_SECRET_KEY` está vazio/ausente
  - [ ] `get_callback_handler` retorna uma instância de `CallbackHandler` quando ambas as keys estão setadas (com `LANGFUSE_HOST` default de `http://localhost:3100` quando não setado)
  - [ ] `build_trace_metadata(trigger)` para um `SimulationEvent` com todos os campos retorna dict com as 5 chaves esperadas e valores iguais aos do trigger
  - [ ] `extract_session_id(trigger)` retorna o `order_id` (string) quando o payload contém; retorna `None` para payload vazio, sem `order_id`, ou com `order_id=None`
- [ ] `backend/tests/unit/agents/test_base.py` ganha:
  - [ ] `test_build_agent_graph_without_langfuse_handler_has_no_callbacks` — simula handler `None`, verifica que `ChatOpenAI` foi instanciado sem `callbacks` (ou com lista vazia), sem warning/erro
  - [ ] `test_build_agent_graph_with_langfuse_handler_injects_callback` — simula handler válido, verifica que `ChatOpenAI` recebeu `callbacks` contendo o handler
- [ ] Todos os testes existentes (820) continuam passando — a instrumentação não quebra nenhum fluxo atual porque os testes não setam as env vars

### Documentação

- [ ] `README.md` ganha seção **Observability (optional)** explicando:
  - [ ] Que Langfuse é opcional e por quê existe (debug + métricas de agentes)
  - [ ] Como subir: `docker compose up -d langfuse-web langfuse-worker` (ou `up -d` inteiro, que sobe tudo)
  - [ ] Como gerar as keys iniciais: acessar `http://localhost:3100`, criar user admin local, criar projeto, copiar `public_key` e `secret_key` para o `backend/.env`
  - [ ] Como desativar: deixar as env vars vazias — sistema roda normalmente
- [ ] `.specs/state.md` feature 31 atualizada para `done` ao fim da implementação

---

## Fora do Escopo

- **Dashboards customizados no frontend** — usa a UI nativa do Langfuse em `localhost:3100`; integrar métricas na HUD do Nexus Twin fica para feature futura
- **Eval datasets posthoc** — Langfuse suporta, mas setup de pipeline de avaliação não entra aqui
- **Métricas do engine não-LLM** — tick duration, DB query latency, queue depths não vão para Langfuse; Prometheus/Grafana seria o caminho tradicional em feature futura separada
- **Modo SaaS** — apenas self-hosted via Docker Compose; plugar em Langfuse Cloud requer só mudar `LANGFUSE_HOST` e as keys, mas documentação específica não entra aqui
- **Alertas e webhooks** — Langfuse suporta, mas config de alertas fica fora
- **Tracing de chamadas não-LLM** (repositories, publisher Redis) — só os spans gerados pelo `ChatOpenAI` callback do LangChain são instrumentados automaticamente; instrumentação manual de outras camadas com OpenTelemetry fica para feature futura
- **Rotação de keys e gestão de users** — user admin único local; gestão multi-tenant fica fora
