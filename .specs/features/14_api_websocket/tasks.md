# Tasks — Feature 14: API WebSocket

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — arquitetura (§4.5 Redis Pub/Sub, §4.6 API & Realtime), estrutura de pastas (§3), convencoes (§8)
- `.specs/features/14_api_websocket/specs.md` — criterios de aceitacao
- `.specs/design.md §3` — formato das mensagens WebSocket (`WSMessage`, payloads por canal, mensagens do cliente)
- `.specs/design.md §5` — canais Redis Pub/Sub (nomes, publishers, subscribers, fluxo geral)
- `backend/src/simulation/publisher.py` — referencia do formato publicado nos canais Redis
- `backend/src/main.py` — entry point onde a rota sera registrada e o lifespan configurado
- `backend/src/database/session.py` — referencia de como variaveis de ambiente sao lidas

---

## Plano de Execucao

Grupo 1 e a fase de testes (TDD Phase 1) — parar apos criar os testes e aguardar aprovacao.
Grupo 2 e a implementacao — executar somente apos aprovacao dos testes.

---

### Grupo 1 — Testes (TDD Phase 1)

**Tarefa:** Escrever testes unitarios para o endpoint WebSocket e o gerenciador de conexoes.

1. Criar `backend/tests/unit/api/__init__.py` (se nao existir) e `backend/tests/unit/api/test_websocket.py`

2. Testar `ConnectionManager`:
   - `connect(ws)` adiciona o cliente ao registro interno; `disconnect(ws)` o remove
   - `broadcast(channel, payload)` envia `WSMessage` apenas para clientes subscritos naquele canal
   - Por padrao (sem mensagem `subscribe`), um cliente recem-conectado recebe mensagens de todos os tres canais (`world_state`, `agent_decisions`, `events`)
   - Apos `set_channels(ws, ["world_state"])`, o cliente recebe apenas mensagens do canal `world_state` — mensagens de `agent_decisions` e `events` nao sao enviadas
   - Multiplos clientes com subscriptions diferentes recebem apenas seus canais respectivos
   - `broadcast` com canal desconhecido nao causa erro

3. Testar endpoint WebSocket (`/ws`):
   - Conexao e aceita com sucesso (status 101)
   - Enviar `{ "type": "ping" }` resulta em resposta `{ "type": "pong" }`
   - Enviar `{ "type": "subscribe", "channels": ["events"] }` atualiza a subscription do cliente
   - JSON invalido do cliente nao derruba a conexao
   - Mensagem com tipo desconhecido (`{ "type": "unknown" }`) e ignorada sem erro

Usar mocks para `WebSocket` (starlette) nos testes do `ConnectionManager`. Para testes do endpoint, usar `TestClient` do Starlette com WebSocket ou `httpx.ASGITransport`.

**Parar aqui. Nao implementar codigo de producao. Aguardar aprovacao do usuario.**

---

### Grupo 2 — Implementacao

**Tarefa:** Implementar o endpoint WebSocket com subscriber Redis e gerenciador de conexoes.

1. Implementar `backend/src/api/websocket.py`:

   a. Classe `ConnectionManager`:
      - `__init__()`: inicializa `_clients: dict[WebSocket, set[str]]` (WebSocket -> conjunto de canais subscritos)
      - `ALL_CHANNELS: set[str] = {"world_state", "agent_decisions", "events"}`
      - `async connect(ws: WebSocket) -> None`: chama `ws.accept()`, registra com subscription padrao (todos os canais)
      - `disconnect(ws: WebSocket) -> None`: remove o cliente do dict (silencioso se nao existe)
      - `set_channels(ws: WebSocket, channels: list[str]) -> None`: atualiza a subscription do cliente (intersectar com `ALL_CHANNELS` para ignorar canais invalidos)
      - `async broadcast(channel: str, payload: str) -> None`: para cada cliente subscrito no `channel`, envia `{"channel": channel, "payload": json.loads(payload)}` via `ws.send_json()`; em caso de erro ao enviar, desconecta o cliente silenciosamente

   b. Mapeamento de canal Redis -> canal WSMessage:
      - `REDIS_TO_WS = {"nexus:world_state": "world_state", "nexus:agent_decisions": "agent_decisions", "nexus:events": "events"}`

   c. Funcao `async redis_subscriber(redis_client, manager: ConnectionManager) -> None`:
      - Cria pubsub via `redis_client.pubsub()`
      - Assina os tres canais: `nexus:world_state`, `nexus:agent_decisions`, `nexus:events`
      - Loop infinito com `pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)`
      - Ao receber mensagem do tipo `"message"`: extrai `channel` e `data`, mapeia via `REDIS_TO_WS`, chama `manager.broadcast(ws_channel, data)`
      - Tratamento de erro: log via Loguru e continua o loop (nao quebra por erro transitorio)

   d. Endpoint `websocket_endpoint(ws: WebSocket)`:
      - Obtem o `ConnectionManager` do `app.state`
      - `await manager.connect(ws)`
      - Logger: `"WebSocket client connected"`
      - Try/except `WebSocketDisconnect`:
        - Loop de recebimento: `data = await ws.receive_text()`
        - Parse JSON; se falhar, ignora
        - Se `type == "ping"`: `await ws.send_json({"type": "pong"})`
        - Se `type == "subscribe"` e `channels` e lista: `manager.set_channels(ws, channels)`
        - Qualquer outro tipo: ignora
      - No disconnect/exception: `manager.disconnect(ws)`, log `"WebSocket client disconnected"`

2. Atualizar `backend/src/main.py`:

   a. No lifespan (startup):
      - Importar `redis.asyncio as aioredis`
      - Criar cliente Redis: `app.state.redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))`
      - Criar manager: `app.state.ws_manager = ConnectionManager()`
      - Iniciar subscriber: `app.state.redis_subscriber_task = asyncio.create_task(redis_subscriber(app.state.redis, app.state.ws_manager))`

   b. No lifespan (shutdown):
      - Cancelar task: `app.state.redis_subscriber_task.cancel()`
      - Fechar Redis: `await app.state.redis.close()`

   c. Registrar a rota WebSocket:
      - `app.add_api_websocket_route("/ws", websocket_endpoint)` ou importar como router e registrar sem prefixo
      - **Nao** usar o prefixo `/api/v1` — endpoint raiz `/ws`

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos.
Todos os testes passam com `pytest`.
Atualizar `state.md`: setar o status da feature `14` para `done`.
