# Feature 14 — API WebSocket

## Objetivo

Implementar o endpoint WebSocket (`GET /ws`) que conecta o dashboard ao backend em tempo real. O handler assina os tres canais Redis Pub/Sub (`nexus:world_state`, `nexus:agent_decisions`, `nexus:events`) e faz forward das mensagens para os clientes WebSocket conectados. Clientes podem filtrar canais via mensagem `subscribe` e manter a conexao viva via `ping`. Esta feature e a ponte entre o simulation engine (que ja publica nos canais Redis desde a feature 07) e o frontend (que consome via WebSocket nas features 16-18).

---

## Criterios de Aceitacao

### Backend

- [ ] Endpoint `GET /ws` aceita conexao WebSocket e mantem a conexao aberta
- [ ] Ao conectar, o servidor assina os tres canais Redis: `nexus:world_state`, `nexus:agent_decisions`, `nexus:events` (`design.md §5`)
- [ ] Mensagens recebidas dos canais Redis sao encapsuladas no formato `WSMessage` e enviadas ao cliente:
  ```json
  { "channel": "world_state" | "agent_decisions" | "events", "payload": <objeto JSON> }
  ```
  Conforme `design.md §3` — o campo `channel` usa o nome sem o prefixo `nexus:`
- [ ] Cliente pode enviar `{ "type": "subscribe", "channels": ["world_state", "agent_decisions"] }` para filtrar quais canais recebe — canais nao listados sao silenciados para aquele cliente
- [ ] Por padrao (sem mensagem `subscribe`), o cliente recebe mensagens de todos os tres canais
- [ ] Cliente pode enviar `{ "type": "ping" }` e recebe `{ "type": "pong" }` como resposta
- [ ] Multiplos clientes podem estar conectados simultaneamente, cada um com suas proprias subscriptions independentes
- [ ] Ao desconectar (graceful ou abrupto), o cliente e removido do gerenciamento sem afetar os demais
- [ ] Erros de parsing de mensagem do cliente (JSON invalido, tipo desconhecido) sao ignorados silenciosamente — sem derrubar a conexao
- [ ] Cliente Redis Pub/Sub e criado no lifespan do app FastAPI e compartilhado entre todas as conexoes WebSocket
- [ ] Rota WebSocket registrada em `main.py` diretamente no app (sem prefixo `/api/v1` — endpoint raiz `/ws`)
- [ ] Logs via Loguru: conexao aceita, desconexao, erro de Redis

---

## Fora do Escopo

- Frontend WebSocket client (`hooks/useWorldSocket.ts`, `store/worldStore.ts`) — features 16-18
- Funcoes de publicacao Redis (`simulation/publisher.py`) — ja implementadas na feature 07
- Autenticacao/autorizacao de conexoes WebSocket
- Celery workers — feature 15
- Compressao de mensagens WebSocket (per-message deflate)
- Reconexao automatica pelo servidor — responsabilidade do cliente
