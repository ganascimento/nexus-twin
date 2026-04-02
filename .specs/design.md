# Nexus Twin — Design Document

> Documento de referência compartilhado entre todas as features. Descreve a estrutura técnica do sistema: banco de dados, endpoints, workers, pub/sub, repositories, services, agentes e guardrails.

---

## 1. Diagrama de Tabelas

### Visão geral das relações

```
materials ──────────────────────────────────────────────────────────────────────┐
    │                                                                            │
    ├──< factory_products (material_id FK)                                       │
    ├──< warehouse_accepted_materials (material_id FK)                           │
    └──< store_sold_materials (material_id FK)                                   │
                                                                                 │
factories ──< factory_products                                                   │
    │                                                                            │
    ├──< trucks (factory_id FK, nullable — proprietários)                        │
    └──< factory_partner_warehouses (factory_id FK, warehouse_id FK)             │
                                                                                 │
warehouses ──< warehouse_accepted_materials                                      │
    └──< factory_partner_warehouses                                              │
                                                                                 │
stores ──< store_sold_materials                                                  │
                                                                                 │
trucks ──< routes (truck_id FK)                                                  │
                                                                                 │
events ──< (entity_id polimórfico — factory/warehouse/store/truck)               │
routes ──< (origem/destino polimórficos — qualquer entidade com lat/lng)         │
agent_decisions ──< (entity_id polimórfico)                                      │
```

---

### `materials`

| Coluna       | Tipo           | Constraints            | Descrição                             |
| ------------ | -------------- | ---------------------- | ------------------------------------- |
| `id`         | `VARCHAR(50)`  | PK                     | Slug único (ex: `tijolos`, `cimento`) |
| `name`       | `VARCHAR(100)` | NOT NULL               | Nome de exibição                      |
| `is_active`  | `BOOLEAN`      | NOT NULL, DEFAULT true | Se aparece nos combos do dashboard    |
| `created_at` | `TIMESTAMPTZ`  | NOT NULL, DEFAULT now  |                                       |

---

### `factories`

| Coluna       | Tipo           | Constraints | Descrição                                    |
| ------------ | -------------- | ----------- | -------------------------------------------- |
| `id`         | `VARCHAR(50)`  | PK          | Slug (ex: `factory-001`)                     |
| `name`       | `VARCHAR(100)` | NOT NULL    |                                              |
| `lat`        | `FLOAT`        | NOT NULL    | Latitude                                     |
| `lng`        | `FLOAT`        | NOT NULL    | Longitude                                    |
| `status`     | `VARCHAR(20)`  | NOT NULL    | `operating` / `stopped` / `reduced_capacity` |
| `created_at` | `TIMESTAMPTZ`  | NOT NULL    |                                              |
| `updated_at` | `TIMESTAMPTZ`  | NOT NULL    |                                              |

### `factory_products`

| Coluna                    | Tipo          | Constraints      | Descrição                             |
| ------------------------- | ------------- | ---------------- | ------------------------------------- |
| `factory_id`              | `VARCHAR(50)` | PK, FK→factories |                                       |
| `material_id`             | `VARCHAR(50)` | PK, FK→materials |                                       |
| `stock`                   | `FLOAT`       | NOT NULL         | Estoque atual em toneladas            |
| `stock_reserved`          | `FLOAT`       | NOT NULL, DEFAULT 0 | Estoque reservado por pedidos confirmados (ton) — subtrai do disponível para evitar double-booking |
| `stock_max`               | `FLOAT`       | NOT NULL         | Capacidade máxima em toneladas        |
| `production_rate_max`     | `FLOAT`       | NOT NULL         | Teto de produção por tick (ton/tick)  |
| `production_rate_current` | `FLOAT`       | NOT NULL         | Produção decidida pelo agente no tick |

### `factory_partner_warehouses`

| Coluna         | Tipo          | Constraints       | Descrição                        |
| -------------- | ------------- | ----------------- | -------------------------------- |
| `factory_id`   | `VARCHAR(50)` | PK, FK→factories  |                                  |
| `warehouse_id` | `VARCHAR(50)` | PK, FK→warehouses |                                  |
| `priority`     | `INTEGER`     | NOT NULL          | Ordem de preferência (1 = maior) |

---

### `warehouses`

| Coluna           | Tipo           | Constraints | Descrição                             |
| ---------------- | -------------- | ----------- | ------------------------------------- |
| `id`             | `VARCHAR(50)`  | PK          |                                       |
| `name`           | `VARCHAR(100)` | NOT NULL    |                                       |
| `lat`            | `FLOAT`        | NOT NULL    |                                       |
| `lng`            | `FLOAT`        | NOT NULL    |                                       |
| `region`         | `VARCHAR(100)` | NOT NULL    | Zona geográfica de atendimento        |
| `capacity_total` | `FLOAT`        | NOT NULL    | Capacidade total combinada (ton)      |
| `status`         | `VARCHAR(20)`  | NOT NULL    | `operating` / `rationing` / `offline` |
| `created_at`     | `TIMESTAMPTZ`  | NOT NULL    |                                       |
| `updated_at`     | `TIMESTAMPTZ`  | NOT NULL    |                                       |

### `warehouse_stocks`

| Coluna         | Tipo          | Constraints       | Descrição                           |
| -------------- | ------------- | ----------------- | ----------------------------------- |
| `warehouse_id` | `VARCHAR(50)` | PK, FK→warehouses |                                     |
| `material_id`  | `VARCHAR(50)` | PK, FK→materials  |                                     |
| `stock`          | `FLOAT`       | NOT NULL          | Estoque atual (ton)                 |
| `stock_reserved` | `FLOAT`       | NOT NULL, DEFAULT 0 | Estoque reservado por pedidos confirmados (ton) — subtrai do disponível para evitar double-booking |
| `min_stock`      | `FLOAT`       | NOT NULL          | Nível mínimo para gatilho preditivo |

---

### `stores`

| Coluna       | Tipo           | Constraints | Descrição                            |
| ------------ | -------------- | ----------- | ------------------------------------ |
| `id`         | `VARCHAR(50)`  | PK          |                                      |
| `name`       | `VARCHAR(100)` | NOT NULL    |                                      |
| `lat`        | `FLOAT`        | NOT NULL    |                                      |
| `lng`        | `FLOAT`        | NOT NULL    |                                      |
| `status`     | `VARCHAR(20)`  | NOT NULL    | `open` / `demand_paused` / `offline` |
| `created_at` | `TIMESTAMPTZ`  | NOT NULL    |                                      |
| `updated_at` | `TIMESTAMPTZ`  | NOT NULL    |                                      |

### `store_stocks`

| Coluna          | Tipo          | Constraints      | Descrição                                  |
| --------------- | ------------- | ---------------- | ------------------------------------------ |
| `store_id`      | `VARCHAR(50)` | PK, FK→stores    |                                            |
| `material_id`   | `VARCHAR(50)` | PK, FK→materials |                                            |
| `stock`         | `FLOAT`       | NOT NULL         | Estoque atual (ton)                        |
| `demand_rate`   | `FLOAT`       | NOT NULL         | Consumo médio por tick (ton/tick)          |
| `reorder_point` | `FLOAT`       | NOT NULL         | Nível de referência para gatilho preditivo |

---

### `trucks`

| Coluna            | Tipo          | Constraints        | Descrição                                              |
| ----------------- | ------------- | ------------------ | ------------------------------------------------------ |
| `id`              | `VARCHAR(50)` | PK                 |                                                        |
| `truck_type`      | `VARCHAR(20)` | NOT NULL           | `proprietario` / `terceiro`                            |
| `capacity_tons`   | `FLOAT`       | NOT NULL           | Capacidade máxima (ton)                                |
| `base_lat`        | `FLOAT`       | NOT NULL           | Latitude da base de repouso                            |
| `base_lng`        | `FLOAT`       | NOT NULL           | Longitude da base de repouso                           |
| `current_lat`     | `FLOAT`       | NOT NULL           | Posição atual                                          |
| `current_lng`     | `FLOAT`       | NOT NULL           | Posição atual                                          |
| `degradation`     | `FLOAT`       | NOT NULL           | Desgaste acumulado (0.0–1.0)                           |
| `breakdown_risk`  | `FLOAT`       | NOT NULL           | Probabilidade de quebra calculada por viagem (0.0–1.0) |
| `status`          | `VARCHAR(20)` | NOT NULL           | `idle` / `evaluating` / `in_transit` / `broken` / `maintenance` |
| `factory_id`      | `VARCHAR(50)` | FK→factories, NULL | Apenas proprietários                                   |
| `cargo`           | `JSONB`       | NULL               | `{product, quantity, origin, destination}` ou null     |
| `active_route_id` | `VARCHAR(50)` | FK→routes, NULL    |                                                        |
| `created_at`      | `TIMESTAMPTZ` | NOT NULL           |                                                        |
| `updated_at`      | `TIMESTAMPTZ` | NOT NULL           |                                                        |

---

### `routes`

| Coluna         | Tipo          | Constraints | Descrição                                        |
| -------------- | ------------- | ----------- | ------------------------------------------------ |
| `id`           | `UUID`        | PK          |                                                  |
| `truck_id`     | `VARCHAR(50)` | FK→trucks   |                                                  |
| `origin_type`  | `VARCHAR(20)` | NOT NULL    | `factory` / `warehouse` / `store`                |
| `origin_id`    | `VARCHAR(50)` | NOT NULL    |                                                  |
| `dest_type`    | `VARCHAR(20)` | NOT NULL    | `factory` / `warehouse` / `store`                |
| `dest_id`      | `VARCHAR(50)` | NOT NULL    |                                                  |
| `path`         | `JSONB`       | NOT NULL    | `[[lng, lat], ...]` — waypoints da rota Valhalla |
| `timestamps`   | `JSONB`       | NOT NULL    | `[ms, ...]` — timestamp em ms para cada waypoint |
| `eta_ticks`    | `INTEGER`     | NOT NULL    | Ticks estimados para conclusão                   |
| `status`       | `VARCHAR(20)` | NOT NULL    | `active` / `completed` / `interrupted`           |
| `started_at`   | `TIMESTAMPTZ` | NOT NULL    |                                                  |
| `completed_at` | `TIMESTAMPTZ` | NULL        |                                                  |

---

### `events`

| Coluna        | Tipo          | Constraints | Descrição                                                      |
| ------------- | ------------- | ----------- | -------------------------------------------------------------- |
| `id`          | `UUID`        | PK          |                                                                |
| `event_type`  | `VARCHAR(50)` | NOT NULL    | Ex: `route_blocked`, `machine_breakdown`, `demand_spike`, etc. |
| `source`      | `VARCHAR(20)` | NOT NULL    | `user` / `master_agent` / `engine`                             |
| `entity_type` | `VARCHAR(20)` | NULL        | `factory` / `warehouse` / `store` / `truck`                    |
| `entity_id`   | `VARCHAR(50)` | NULL        | ID da entidade afetada                                         |
| `payload`     | `JSONB`       | NOT NULL    | Dados específicos do evento                                    |
| `status`      | `VARCHAR(20)` | NOT NULL    | `active` / `resolved`                                          |
| `tick_start`  | `INTEGER`     | NOT NULL    | Tick em que o evento foi criado                                |
| `tick_end`    | `INTEGER`     | NULL        | Tick em que foi resolvido                                      |
| `created_at`  | `TIMESTAMPTZ` | NOT NULL    |                                                                |

---

### `agent_decisions`

| Coluna       | Tipo          | Constraints | Descrição                                                     |
| ------------ | ------------- | ----------- | ------------------------------------------------------------- |
| `id`         | `UUID`        | PK          |                                                               |
| `agent_type` | `VARCHAR(20)` | NOT NULL    | `factory` / `warehouse` / `store` / `truck` / `master`        |
| `entity_id`  | `VARCHAR(50)` | NOT NULL    | ID da entidade que tomou a decisão                            |
| `tick`       | `INTEGER`     | NOT NULL    | Tick em que a decisão foi tomada                              |
| `event_type` | `VARCHAR(50)` | NOT NULL    | Gatilho que acordou o agente                                  |
| `action`     | `VARCHAR(50)` | NOT NULL    | Ex: `request_resupply`, `accept_contract`, `start_production` |
| `payload`    | `JSONB`       | NOT NULL    | Detalhes da decisão (quantidades, destinos, motivos)          |
| `reasoning`  | `TEXT`        | NULL        | Raciocínio do LLM (opcional, para debug)                      |
| `created_at` | `TIMESTAMPTZ` | NOT NULL    |                                                               |

---

### `pending_orders`

| Coluna             | Tipo          | Constraints         | Descrição                                          |
| ------------------ | ------------- | ------------------- | -------------------------------------------------- |
| `id`               | `UUID`        | PK                  |                                                    |
| `requester_type`   | `VARCHAR(20)` | NOT NULL            | `store` / `warehouse`                              |
| `requester_id`     | `VARCHAR(50)` | NOT NULL            |                                                    |
| `target_type`      | `VARCHAR(20)` | NOT NULL            | `warehouse` / `factory`                            |
| `target_id`        | `VARCHAR(50)` | NOT NULL            |                                                    |
| `material_id`      | `VARCHAR(50)` | FK→materials        |                                                    |
| `quantity_tons`    | `FLOAT`       | NOT NULL            |                                                    |
| `status`              | `VARCHAR(20)` | NOT NULL            | `pending` / `confirmed` / `rejected` / `delivered` / `cancelled` |
| `age_ticks`           | `INTEGER`     | NOT NULL, DEFAULT 0 | Ticks desde a criação                              |
| `retry_after_tick`    | `INTEGER`     | NULL                | Tick a partir do qual pode retentar após rejeição  |
| `rejection_reason`    | `TEXT`        | NULL                |                                                    |
| `cancellation_reason` | `TEXT`        | NULL                | Motivo do cancelamento — ex: `target_deleted`, `requester_deleted` |
| `eta_ticks`           | `INTEGER`     | NULL                | ETA confirmado pelo target                         |
| `created_at`       | `TIMESTAMPTZ` | NOT NULL            |                                                    |
| `updated_at`       | `TIMESTAMPTZ` | NOT NULL            |                                                    |

---

## 2. Endpoints HTTP

Base URL: `/api/v1`

---

### Simulação — `/simulation`

| Método  | Path                 | Descrição                                                         |
| ------- | -------------------- | ----------------------------------------------------------------- |
| `POST`  | `/simulation/start`  | Inicia o loop de ticks                                            |
| `POST`  | `/simulation/stop`   | Para o loop de ticks                                              |
| `POST`  | `/simulation/tick`   | Avança manualmente 1 tick (só funciona com simulação parada)      |
| `GET`   | `/simulation/status` | Retorna estado atual: `running`/`stopped`, tick atual, velocidade |
| `PATCH` | `/simulation/speed`  | Ajusta `tick_interval_seconds` (mínimo: 10)                       |

---

### Estado do Mundo — `/world`

| Método | Path              | Descrição                                             |
| ------ | ----------------- | ----------------------------------------------------- |
| `GET`  | `/world/snapshot` | Retorna o `WorldState` completo do tick atual         |
| `GET`  | `/world/tick`     | Retorna o número do tick atual e o timestamp simulado |

---

### Materiais — `/materials`

| Método  | Path                         | Descrição                                                      |
| ------- | ---------------------------- | -------------------------------------------------------------- |
| `GET`   | `/materials`                 | Lista todos os materiais (aceita `?active_only=true`)          |
| `POST`  | `/materials`                 | Cria novo material                                             |
| `PATCH` | `/materials/{id}`            | Edita nome de um material                                      |
| `PATCH` | `/materials/{id}/deactivate` | Desativa material (impede exclusão se há entidades vinculadas) |

---

### Entidades — `/entities`

#### Fábricas

| Método   | Path                       | Descrição                                                   |
| -------- | -------------------------- | ----------------------------------------------------------- |
| `GET`    | `/entities/factories`      | Lista todas as fábricas com estoque e status atuais         |
| `GET`    | `/entities/factories/{id}` | Detalhe de uma fábrica (inclui produtos, caminhões, ordens) |
| `POST`   | `/entities/factories`      | Cria nova fábrica                                           |
| `PATCH`  | `/entities/factories/{id}` | Edita materiais produzidos, capacidades, armazéns parceiros |
| `DELETE` | `/entities/factories/{id}` | Remove fábrica (redistribui pedidos pendentes)              |

#### Armazéns

| Método   | Path                        | Descrição                                                 |
| -------- | --------------------------- | --------------------------------------------------------- |
| `GET`    | `/entities/warehouses`      | Lista todos os armazéns com estoque e status atuais       |
| `GET`    | `/entities/warehouses/{id}` | Detalhe de um armazém                                     |
| `POST`   | `/entities/warehouses`      | Cria novo armazém                                         |
| `PATCH`  | `/entities/warehouses/{id}` | Edita materiais aceitos, capacidades, mínimos por produto |
| `DELETE` | `/entities/warehouses/{id}` | Remove armazém (lojas da região precisam se reajustar)    |

#### Lojas

| Método   | Path                    | Descrição                                         |
| -------- | ----------------------- | ------------------------------------------------- |
| `GET`    | `/entities/stores`      | Lista todas as lojas com estoque e status atuais  |
| `GET`    | `/entities/stores/{id}` | Detalhe de uma loja                               |
| `POST`   | `/entities/stores`      | Cria nova loja                                    |
| `PATCH`  | `/entities/stores/{id}` | Edita materiais vendidos, demanda, reorder points |
| `DELETE` | `/entities/stores/{id}` | Remove loja (cancela pedidos pendentes)           |

#### Caminhões

| Método   | Path                    | Descrição                                                        |
| -------- | ----------------------- | ---------------------------------------------------------------- |
| `GET`    | `/entities/trucks`      | Lista todos os caminhões com posição, carga e degradação         |
| `GET`    | `/entities/trucks/{id}` | Detalhe de um caminhão (inclui rota ativa e histórico)           |
| `POST`   | `/entities/trucks`      | Adiciona novo caminhão (proprietário ou terceiro)                |
| `DELETE` | `/entities/trucks/{id}` | Remove caminhão (se em trânsito, dispara reassinalação de carga) |

#### Estoques (ajuste manual)

| Método  | Path                              | Descrição                               |
| ------- | --------------------------------- | --------------------------------------- |
| `PATCH` | `/entities/factories/{id}/stock`  | Ajusta estoque de um produto da fábrica |
| `PATCH` | `/entities/warehouses/{id}/stock` | Ajusta estoque de um produto do armazém |
| `PATCH` | `/entities/stores/{id}/stock`     | Ajusta estoque de um produto da loja    |

---

### Caos — `/chaos`

| Método | Path                         | Descrição                                               |
| ------ | ---------------------------- | ------------------------------------------------------- |
| `GET`  | `/chaos/events`              | Lista eventos de caos ativos                            |
| `POST` | `/chaos/events`              | Injeta um novo evento de caos (somente eventos manuais) |
| `POST` | `/chaos/events/{id}/resolve` | Resolve/cancela um evento de caos em andamento          |

**Payload de criação de evento** (exemplo):

```json
{
  "event_type": "route_blocked",
  "payload": {
    "highway": "SP-330",
    "duration_ticks": 8
  }
}
```

---

### Decisões dos Agentes — `/decisions`

| Método | Path                     | Descrição                                                 |
| ------ | ------------------------ | --------------------------------------------------------- |
| `GET`  | `/decisions`             | Lista decisões recentes (aceita `?entity_id=`, `?limit=`) |
| `GET`  | `/decisions/{entity_id}` | Histórico de decisões de uma entidade específica          |

---

## 3. Rotas WebSocket

### `GET /ws`

Conexão WebSocket única. Após conectar, o backend faz subscribe nos canais Redis e faz forward dos eventos para o cliente.

#### Mensagens enviadas pelo servidor

```typescript
// Tipo base de todas as mensagens
interface WSMessage {
  channel: "world_state" | "agent_decisions" | "events";
  payload: WorldStatePayload | AgentDecisionPayload | EventPayload;
}
```

**Canal `world_state`** — publicado a cada tick pelo engine:

```typescript
interface WorldStatePayload {
  tick: number;
  simulated_timestamp: string; // ISO 8601 no tempo do mundo simulado
  factories: FactorySnapshot[];
  warehouses: WarehouseSnapshot[];
  stores: StoreSnapshot[];
  trucks: TruckSnapshot[]; // inclui posição atual interpolada e cargo ativo
  active_events: ActiveEvent[];
}
```

**Canal `agent_decisions`** — publicado por cada agente ao persistir uma decisão:

```typescript
interface AgentDecisionPayload {
  tick: number;
  agent_type: "factory" | "warehouse" | "store" | "truck" | "master";
  entity_id: string;
  entity_name: string;
  action: string;
  summary: string; // texto legível para o feed do dashboard
  reasoning?: string;
}
```

**Canal `events`** — publicado pelo engine e chaos.py:

```typescript
interface EventPayload {
  event_id: string;
  event_type: string;
  source: "user" | "master_agent" | "engine";
  entity_type?: string;
  entity_id?: string;
  status: "active" | "resolved";
  tick: number;
  description: string;
}
```

#### Mensagens enviadas pelo cliente

```typescript
// Ping para manter a conexão
{ "type": "ping" }

// Subscrever a um subset de canais (padrão: todos)
{ "type": "subscribe", "channels": ["world_state", "agent_decisions"] }
```

---

## 4. Workers (Celery)

Worker: `celery -A src.workers.celery_app worker`

Exclusivo para jobs de background **não-LLM**. O paralelismo de agentes LLM usa `asyncio.create_task` — Celery não entra nesse fluxo.

### `workers/tasks/reports.py`

| Task                         | Trigger                    | Descrição                                                                                                                             |
| ---------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `generate_efficiency_report` | Endpoint REST ou agendado  | Gera relatório de eficiência da simulação (pedidos atendidos vs. atrasados, ruptura de estoque por entidade, utilização de caminhões) |
| `generate_decision_summary`  | Agendado (a cada 24 ticks) | Consolida decisões dos agentes por período, agrupando por tipo de ação                                                                |

### `workers/tasks/exports.py`

| Task                      | Trigger       | Descrição                                                     |
| ------------------------- | ------------- | ------------------------------------------------------------- |
| `export_decision_history` | Endpoint REST | Exporta histórico completo de `agent_decisions` para CSV/JSON |
| `export_event_history`    | Endpoint REST | Exporta histórico de eventos de caos com status de resolução  |
| `export_world_snapshot`   | Endpoint REST | Exporta snapshot do `WorldState` atual em JSON                |

---

## 5. Pub/Sub — Canais Redis

| Canal                   | Publisher                                                | Subscriber         | Conteúdo                                            |
| ----------------------- | -------------------------------------------------------- | ------------------ | --------------------------------------------------- |
| `nexus:world_state`     | `simulation/engine.py` — ao fim de cada tick             | `api/websocket.py` | `WorldStatePayload` completo serializado em JSON    |
| `nexus:agent_decisions` | Cada agente — ao persistir uma decisão (fire-and-forget) | `api/websocket.py` | `AgentDecisionPayload` com ação, entidade, resumo   |
| `nexus:events`          | `simulation/engine.py` + `simulation/chaos.py`           | `api/websocket.py` | `EventPayload` — eventos de caos, alertas, triggers |

**Fluxo geral:**

```
engine.py
  ├── apply_physics()
  ├── evaluate_triggers()
  ├── asyncio.create_task(agent.run_cycle())  ← fire-and-forget
  └── publisher.publish_world_state()  ──► nexus:world_state

agent (background)
  └── persist_decision()
        └── publisher.publish_decision()  ──► nexus:agent_decisions

chaos.py
  └── inject_event() / resolve_event()  ──► nexus:events

api/websocket.py  (subscriber)
  ├── subscribe nexus:world_state    ──► forward para clientes WS
  ├── subscribe nexus:agent_decisions ──► forward para clientes WS
  └── subscribe nexus:events          ──► forward para clientes WS
```

---

## 6. Services

Camada de negócio entre a API/engine e os repositories. Services são classes injetadas via FastAPI Depends. Não acessam o banco diretamente — delegam para a camada de repositories.

Cada service vive em `backend/src/services/<domínio>.py`.

---

### `SimulationService` — `services/simulation.py`

Controla o ciclo de vida do loop de ticks.

| Método                                   | Descrição                                                                |
| ---------------------------------------- | ------------------------------------------------------------------------ |
| `start() → None`                         | Inicia o loop assíncrono de ticks                                        |
| `stop() → None`                          | Para o loop de ticks                                                     |
| `advance_tick() → WorldState`            | Avança 1 tick manualmente (apenas quando parado)                         |
| `set_tick_interval(seconds: int) → None` | Atualiza `TICK_INTERVAL_SECONDS` em runtime (mínimo: 10)                 |
| `get_status() → SimulationStatus`        | Retorna estado atual: running, tick atual, intervalo, timestamp simulado |

---

### `WorldStateService` — `services/world_state.py`

Carrega e monta o `WorldState` completo do PostgreSQL.

| Método                               | Descrição                                                          |
| ------------------------------------ | ------------------------------------------------------------------ |
| `load_world_state() → WorldState`    | Carrega todas as entidades em uma query com joins (evita N+1)      |
| `get_snapshot() → WorldStatePayload` | Serializa `WorldState` para o formato de payload do WebSocket/REST |

---

### `MaterialService` — `services/material.py`

Gerencia o catálogo de materiais.

| Método                                                      | Descrição                                            |
| ----------------------------------------------------------- | ---------------------------------------------------- |
| `list_materials(active_only: bool) → list[Material]`        | Lista materiais, opcionalmente filtrando ativos      |
| `create_material(data: MaterialCreate) → Material`          | Cria novo material                                   |
| `update_material(id: str, data: MaterialUpdate) → Material` | Edita nome de um material                            |
| `deactivate_material(id: str) → Material`                   | Desativa material — falha se há entidades vinculadas |

---

### `FactoryService` — `services/factory.py`

| Método                                                         | Descrição                                         |
| -------------------------------------------------------------- | ------------------------------------------------- |
| `list_factories() → list[Factory]`                             | Lista fábricas com produtos e estoque atuais      |
| `get_factory(id: str) → Factory`                               | Detalhe completo (produtos, caminhões, parceiros) |
| `create_factory(data: FactoryCreate) → Factory`                | Cria fábrica com produtos e armazéns parceiros    |
| `update_factory(id: str, data: FactoryUpdate) → Factory`       | Edita materiais, capacidades, parceiros           |
| `delete_factory(id: str) → None`                               | Remove fábrica: (1) cancela `pending_orders` com `target_id = id` e status `pending`/`confirmed`, definindo `cancellation_reason = 'target_deleted'`; (2) pedidos com caminhão já em trânsito (`status = confirmed` + rota ativa) mantêm status — o caminhão completa a entrega normalmente; (3) publica evento `entity_removed` no canal `nexus:events`; (4) na avaliação do próximo tick, requesters com pedidos cancelados são acordados para buscar alternativas |
| `adjust_stock(id: str, material_id: str, delta: float) → None` | Ajuste manual de estoque por produto              |

---

### `WarehouseService` — `services/warehouse.py`

| Método                                                         | Descrição                                       |
| -------------------------------------------------------------- | ----------------------------------------------- |
| `list_warehouses() → list[Warehouse]`                          | Lista armazéns com estoque atual por produto    |
| `get_warehouse(id: str) → Warehouse`                           | Detalhe completo                                |
| `create_warehouse(data: WarehouseCreate) → Warehouse`          | Cria armazém com materiais aceitos e mínimos    |
| `update_warehouse(id: str, data: WarehouseUpdate) → Warehouse` | Edita materiais, capacidades, mínimos           |
| `delete_warehouse(id: str) → None`                             | Remove armazém: (1) cancela `pending_orders` com `target_id = id` e status `pending`/`confirmed`, definindo `cancellation_reason = 'target_deleted'`; (2) pedidos com caminhão já em trânsito mantêm status — o caminhão completa a entrega e fica `idle` ao chegar; (3) publica evento `entity_removed`; (4) requesters com pedidos cancelados acordam no próximo tick |
| `adjust_stock(id: str, material_id: str, delta: float) → None` | Ajuste manual de estoque por produto            |
| `confirm_order(order_id: UUID, eta_ticks: int) → PendingOrder \| None` | Reserva estoque atomicamente via `UPDATE warehouse_stocks SET stock_reserved = stock_reserved + qty WHERE stock - stock_reserved >= qty`; retorna `None` se estoque disponível insuficiente (sem atualização parcial) |
| `reject_order(order_id: UUID, reason: str) → PendingOrder`     | Rejeita pedido com motivo                       |

---

### `StoreService` — `services/store.py`

| Método                                                         | Descrição                                         |
| -------------------------------------------------------------- | ------------------------------------------------- |
| `list_stores() → list[Store]`                                  | Lista lojas com estoque atual por produto         |
| `get_store(id: str) → Store`                                   | Detalhe completo                                  |
| `create_store(data: StoreCreate) → Store`                      | Cria loja com materiais, demanda e reorder points |
| `update_store(id: str, data: StoreUpdate) → Store`             | Edita materiais, demanda, reorder points          |
| `delete_store(id: str) → None`                                 | Remove loja: cancela pedidos com `requester_id = id` via `OrderService.cancel_orders_from()`; caminhões em trânsito para a loja completam a entrega e ficam `idle` ao chegar; publica evento `entity_removed` |
| `adjust_stock(id: str, material_id: str, delta: float) → None` | Ajuste manual de estoque por produto              |
| `create_order(data: PendingOrderCreate) → PendingOrder`        | Cria pedido de reposição para armazém ou fábrica  |

---

### `TruckService` — `services/truck.py`

| Método                                                    | Descrição                                                      |
| --------------------------------------------------------- | -------------------------------------------------------------- |
| `list_trucks() → list[Truck]`                             | Lista caminhões com posição atual, carga e degradação          |
| `get_truck(id: str) → Truck`                              | Detalhe completo (rota ativa, histórico de decisões)           |
| `create_truck(data: TruckCreate) → Truck`                 | Adiciona caminhão (proprietário ou terceiro)                   |
| `delete_truck(id: str) → None`                            | Remove caminhão; dispara reassinalação de carga se em trânsito |
| `assign_route(truck_id: str, route: RouteCreate) → Route` | Persiste rota Valhalla com timestamps                          |
| `complete_route(truck_id: str) → None`                    | Marca rota como concluída, atualiza posição e degradação       |
| `interrupt_route(truck_id: str, reason: str) → None`      | Interrompe rota por quebra ou bloqueio                         |
| `schedule_maintenance(truck_id: str) → None`              | Inicia manutenção; bloqueia viagens pelo período calculado     |
| `try_lock_for_evaluation(truck_id: str) → bool`           | Wrapper sobre `TruckRepository.try_lock_for_evaluation`; retorna `False` se o caminhão não estava `idle` — o engine descarta a task sem criar o agente |

---

### `ChaosService` — `services/chaos.py`

| Método                                                         | Descrição                                                  |
| -------------------------------------------------------------- | ---------------------------------------------------------- |
| `list_active_events() → list[ChaosEvent]`                      | Lista eventos de caos ativos                               |
| `inject_event(data: ChaosEventCreate) → ChaosEvent`            | Injeta evento com source=`user`                            |
| `inject_autonomous_event(data: ChaosEventCreate) → ChaosEvent \| None` | Check+insert atômico via `SELECT FOR UPDATE` na tabela `events` dentro de uma única transação: lê `count_active()` e `get_last_resolved_autonomous_tick()` com lock antes de inserir; retorna `None` se cooldown não passou ou há evento ativo — **`can_inject_autonomous_event()` não deve ser chamado separadamente** |
| `resolve_event(event_id: UUID) → ChaosEvent`                           | Resolve evento, registra `tick_end`                        |
| `can_inject_autonomous_event() → bool`                                  | Consulta somente-leitura para exibição no dashboard; a verificação de escrita acontece dentro de `inject_autonomous_event` com lock exclusivo |

---

### `PhysicsService` — `services/physics.py`

Cálculos determinísticos sem IA. Chamado pelo engine a cada tick.

| Método                                                                               | Descrição                                                     |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| `apply_physics(world: WorldState) → WorldState`                                      | Ponto de entrada — chama todos os métodos abaixo em sequência |
| `update_truck_positions(trucks: list[Truck], tick: int) → list[Truck]`               | Interpola posições por timestamp da rota ativa                |
| `decrement_store_stocks(stores: list[Store]) → list[Store]`                          | Aplica `demand_rate` em cada produto de cada loja aberta      |
| `produce_factory_stocks(factories: list[Factory]) → list[Factory]`                   | Aplica `production_rate_current` para cada produto            |
| `calculate_degradation(truck: Truck, distance_km: float, cargo_tons: float) → float` | Incremento de degradação proporcional à distância e carga     |
| `calculate_breakdown_risk(degradation: float, route_risk: float) → float`            | Probabilidade de quebra (tabela exponencial do PRD)           |
| `roll_breakdown(truck: Truck) → bool`                                                | Sorteia quebra com base em `breakdown_risk` ao iniciar viagem |
| `calculate_maintenance_ticks(degradation: float) → int`                              | Retorna ticks de imobilização pela tabela do PRD              |

---

### `TriggerEvaluationService` — `services/trigger_evaluation.py`

Avalia, a cada tick, quais agentes devem ser acordados.

| Método                                                             | Descrição                                                                                    |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `evaluate_all(world: WorldState) → list[AgentTrigger]`             | Ponto de entrada — agrega todos os triggers do tick; inclui triggers de `order_cancelled_target_deleted` para agentes com pedidos cancelados por deleção de entidade (ver seção 10.4) |
| `evaluate_store_triggers(store: Store) → list[AgentTrigger]`       | `(stock[p] - reorder_point[p]) / demand_rate[p] < lead_time × 1.5`; também emite trigger `order_cancelled_target_deleted` se a loja tiver pedidos com `status = 'cancelled'` não processados |
| `evaluate_warehouse_triggers(wh: Warehouse) → list[AgentTrigger]`  | Para cada produto: `(stock[p] - stock_reserved[p] - min_stock[p]) / outbound_rate[p] < lead_time × 1.5` onde `outbound_rate[p]` é a média das saídas dos últimos 6 ticks (janela deslizante, não valor estático) — evita oscilação por demanda temporária baixa |
| `evaluate_factory_triggers(factory: Factory) → list[AgentTrigger]` | Estoque de saída perto do máximo; pedidos urgentes de armazéns                               |
| `evaluate_truck_triggers(truck: Truck) → list[AgentTrigger]`       | Eventos pendentes: `route_blocked`, `arrived`, `breakdown`, `new_order`, `contract_proposal`; para `contract_proposal`, chama `TruckService.try_lock_for_evaluation()` antes de emitir o trigger — se retornar `False`, o trigger é descartado (caminhão já em avaliação) |

---

### `OrderService` — `services/order.py`

Gerencia o ciclo de vida dos `pending_orders`.

| Método                                                                       | Descrição                                           |
| ---------------------------------------------------------------------------- | --------------------------------------------------- |
| `create_order(data: PendingOrderCreate) → PendingOrder`                      | Cria pedido, age_ticks=0                            |
| `increment_age_ticks(tick: int) → None`                                      | Incrementa `age_ticks` de todos os pedidos ativos   |
| `get_pending_orders_for(target_id: str) → list[PendingOrder]`                | Pedidos aguardando uma entidade específica          |
| `confirm_order(order_id: UUID, eta_ticks: int) → PendingOrder`                            | Muda status para `confirmed`, salva ETA; a reserva de estoque é feita pelo `WarehouseService.confirm_order()` antes de chamar este método |
| `reject_order(order_id: UUID, reason: str, retry_after: int) → PendingOrder`              | Muda status para `rejected`, salva motivo e backoff |
| `mark_delivered(order_id: UUID) → PendingOrder`                                           | Muda status para `delivered`; libera `stock_reserved` na entidade de origem |
| `cancel_orders_targeting(target_id: str, reason: str) → list[PendingOrder]`               | Cancela pedidos `pending`/`confirmed` cujo `target_id` é a entidade removida; pedidos com rota de caminhão já ativa são ignorados (entrega prossegue); retorna lista de requesters afetados |
| `cancel_orders_from(requester_id: str, reason: str) → list[PendingOrder]`                 | Cancela pedidos emitidos por uma entidade removida (ex: loja deletada) |

---

### `RouteService` — `services/route.py`

Integração com Valhalla para cálculo de rotas reais.

| Método                                                                   | Descrição                                                                           |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `get_route(origin: LatLng, destination: LatLng) → ValhallRoute`          | Chama Valhalla (`POST /route`, `costing: "truck"`) — retorna polyline com waypoints |
| `calculate_timestamps(path: list[LatLng], speed_kmh: float) → list[int]` | Calcula timestamp em ms para cada waypoint                                          |
| `persist_route(truck_id: str, route_data: RouteCreate) → Route`          | Persiste rota no PostGIS                                                            |
| `calculate_eta_ticks(total_distance_km: float, speed_kmh: float) → int`  | Converte distância em ticks simulados                                               |

---

## 7. Repositories

Camada de acesso ao banco. Cada repository encapsula todas as queries SQLAlchemy de uma entidade ou agregado. Services nunca importam a `AsyncSession` diretamente — sempre delegam para um repository.

Cada repository vive em `backend/src/repositories/<entidade>.py`.

---

### `MaterialRepository` — `repositories/material.py`

| Método                                                       | Descrição                                              |
|--------------------------------------------------------------|--------------------------------------------------------|
| `get_all(active_only: bool) → list[Material]`                | Lista materiais                                        |
| `get_by_id(id: str) → Material \| None`                      | Busca por id                                           |
| `create(data: dict) → Material`                              | Insere novo material                                   |
| `update(id: str, data: dict) → Material`                     | Atualiza campos                                        |
| `has_linked_entities(id: str) → bool`                        | Verifica se há fábricas/armazéns/lojas vinculadas      |

---

### `FactoryRepository` — `repositories/factory.py`

| Método                                                                        | Descrição                                                       |
|-------------------------------------------------------------------------------|-----------------------------------------------------------------|
| `get_all() → list[Factory]`                                                   | Lista fábricas com produtos (join `factory_products`)           |
| `get_by_id(id: str) → Factory \| None`                                        | Detalhe com produtos, caminhões vinculados e parceiros          |
| `create(data: dict) → Factory`                                                | Insere fábrica + `factory_products` + `factory_partner_warehouses` |
| `update(id: str, data: dict) → Factory`                                       | Atualiza campos + reconcilia products/partners                  |
| `delete(id: str) → None`                                                      | Remove fábrica e registros dependentes                          |
| `update_product_stock(factory_id: str, material_id: str, delta: float) → None`| Incrementa/decrementa `factory_products.stock`                  |
| `update_production_rate(factory_id: str, material_id: str, rate: float) → None`| Atualiza `production_rate_current`                             |

---

### `WarehouseRepository` — `repositories/warehouse.py`

| Método                                                                          | Descrição                                                      |
|---------------------------------------------------------------------------------|----------------------------------------------------------------|
| `get_all() → list[Warehouse]`                                                   | Lista armazéns com estoque por produto                         |
| `get_by_id(id: str) → Warehouse \| None`                                        | Detalhe com `warehouse_stocks`                                 |
| `create(data: dict) → Warehouse`                                                | Insere armazém + `warehouse_stocks`                            |
| `update(id: str, data: dict) → Warehouse`                                       | Atualiza campos + reconcilia stocks                            |
| `delete(id: str) → None`                                                        | Remove armazém                                                 |
| `update_stock(warehouse_id: str, material_id: str, delta: float) → None`        | Incrementa/decrementa estoque de um produto                    |
| `get_total_stock_used(warehouse_id: str) → float`                               | Soma do estoque atual de todos os produtos (verifica capacidade)|

---

### `StoreRepository` — `repositories/store.py`

| Método                                                                      | Descrição                                               |
|-----------------------------------------------------------------------------|---------------------------------------------------------|
| `get_all() → list[Store]`                                                   | Lista lojas com estoque por produto                     |
| `get_by_id(id: str) → Store \| None`                                        | Detalhe com `store_stocks`                              |
| `create(data: dict) → Store`                                                | Insere loja + `store_stocks`                            |
| `update(id: str, data: dict) → Store`                                       | Atualiza campos + reconcilia stocks                     |
| `delete(id: str) → None`                                                    | Remove loja                                             |
| `update_stock(store_id: str, material_id: str, delta: float) → None`        | Incrementa/decrementa estoque de um produto             |

---

### `TruckRepository` — `repositories/truck.py`

| Método                                                                         | Descrição                                              |
|--------------------------------------------------------------------------------|--------------------------------------------------------|
| `get_all() → list[Truck]`                                                      | Lista todos os caminhões                               |
| `get_by_id(id: str) → Truck \| None`                                           |                                                        |
| `get_by_factory(factory_id: str) → list[Truck]`                                | Caminhões proprietários de uma fábrica                 |
| `create(data: dict) → Truck`                                                   | Insere caminhão                                        |
| `delete(id: str) → None`                                                       | Remove caminhão                                        |
| `update_status(id: str, status: str) → None`                                   | Atualiza `status`                                                   |
| `try_lock_for_evaluation(truck_id: str) → bool`                                | `UPDATE trucks SET status = 'evaluating' WHERE id = ? AND status = 'idle'` — retorna `True` se bem-sucedido (caminhão era `idle`), `False` se já estava em outro estado; garante que só uma task concurrent avalie o caminhão |
| `update_position(id: str, lat: float, lng: float) → None`                      | Atualiza `current_lat/lng`                             |
| `update_degradation(id: str, degradation: float, breakdown_risk: float) → None`| Atualiza desgaste e risco                              |
| `set_cargo(id: str, cargo: dict \| None) → None`                               | Define ou limpa a carga atual                          |
| `set_active_route(id: str, route_id: UUID \| None) → None`                     | Vincula ou desvincula rota ativa                       |

---

### `RouteRepository` — `repositories/route.py`

| Método                                                              | Descrição                                        |
|---------------------------------------------------------------------|--------------------------------------------------|
| `create(data: dict) → Route`                                        | Persiste rota com path e timestamps (PostGIS)    |
| `get_by_id(id: UUID) → Route \| None`                               |                                                  |
| `get_active_by_truck(truck_id: str) → Route \| None`                | Rota com status `active` do caminhão             |
| `update_status(id: UUID, status: str, completed_at=None) → None`    | Marca rota como `completed` ou `interrupted`     |

---

### `OrderRepository` — `repositories/order.py`

| Método                                                                            | Descrição                                              |
|-----------------------------------------------------------------------------------|--------------------------------------------------------|
| `create(data: dict) → PendingOrder`                                               | Cria pedido com `age_ticks=0`                          |
| `get_by_id(id: UUID) → PendingOrder \| None`                                      |                                                        |
| `get_pending_for_target(target_id: str) → list[PendingOrder]`                     | Pedidos aguardando uma entidade                        |
| `get_pending_for_requester(requester_id: str) → list[PendingOrder]`               | Pedidos emitidos por uma entidade                      |
| `increment_all_age_ticks() → None`                                                | Bulk update — incrementa `age_ticks` de todos os ativos|
| `update_status(id: UUID, status: str, **kwargs) → PendingOrder`                   | Atualiza status + campos opcionais (eta, rejection_reason, cancellation_reason) |
| `bulk_cancel_by_target(target_id: str, reason: str, skip_active_routes: bool = True) → list[UUID]` | Cancela em bulk pedidos de um target; se `skip_active_routes=True`, ignora pedidos onde já há caminhão em rota (entrega prossegue); retorna IDs dos requesters afetados |
| `bulk_cancel_by_requester(requester_id: str, reason: str) → None`                 | Cancela em bulk pedidos emitidos por uma entidade removida |

---

### `EventRepository` — `repositories/event.py`

| Método                                                              | Descrição                                              |
|---------------------------------------------------------------------|--------------------------------------------------------|
| `get_active() → list[ChaosEvent]`                                   | Eventos de caos ativos                                 |
| `create(data: dict) → ChaosEvent`                                   | Persiste novo evento                                   |
| `resolve(id: UUID, tick_end: int) → ChaosEvent`                     | Marca evento como resolvido                            |
| `count_active() → int`                                              | Verifica empilhamento (máx 1 evento autônomo por vez)  |
| `get_last_resolved_autonomous_tick() → int \| None`                 | Tick de resolução do último evento autônomo (cooldown) |

---

### `AgentDecisionRepository` — `repositories/agent_decision.py`

| Método                                                                             | Descrição                                              |
|------------------------------------------------------------------------------------|--------------------------------------------------------|
| `create(data: dict) → AgentDecision`                                               | Persiste decisão de um agente                          |
| `get_recent_by_entity(entity_id: str, limit: int) → list[AgentDecision]`           | Últimas N decisões de uma entidade (memória do agente) |
| `get_all(entity_id: str \| None, limit: int) → list[AgentDecision]`                | Lista decisões com filtro opcional por entidade        |

---

## 8. Camada de Agentes — MAS (Multi-Agent System)

### 7.1 Schema do Grafo (TypedDict)

O `AgentState` é o **contrato de interface** entre os nós do `StateGraph`. Todo dado que trafega entre `perceive`, `decide` e `act` passa por ele.

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from pydantic import BaseModel

class AgentState(TypedDict):
    # Contexto de entrada — preenchido pelo nó perceive
    world_state: WorldStateSlice        # Slice do WorldState relevante para este agente
    entity_id: str                      # ID da entidade que este agente representa
    entity_type: Literal["factory", "warehouse", "store", "truck"]
    trigger_event: str                  # Evento que acordou este agente
    current_tick: int

    # Histórico de mensagens — gerenciado pelo LangGraph (add_messages faz append)
    messages: Annotated[list, add_messages]

    # Memória de curto prazo — injetada no system prompt
    decision_history: list[DecisionMemory]  # Últimas N decisões desta entidade

    # Resultado do ciclo — preenchido pelo nó act
    decision: AgentDecision | None

    # Metadados de controle
    fast_path_taken: bool               # True se resolvido sem chamar o LLM
    error: str | None                   # Erro de guardrail ou exception

class WorldStateSlice(TypedDict):
    """Recorte do WorldState relevante para o agente. Diferente por tipo."""
    entity: dict                        # Estado atual da entidade (serializado)
    related_entities: list[dict]        # Armazéns parceiros, lojas da região, etc.
    active_events: list[dict]           # Eventos de caos ativos que afetam este agente
    pending_orders: list[dict]          # Pedidos pendentes relevantes para este agente

class DecisionMemory(TypedDict):
    tick: int
    event_type: str
    action: str
    summary: str                        # Texto legível da decisão anterior

class AgentDecision(TypedDict):
    action: str
    payload: dict                       # Dados específicos por tipo de ação
```

---

### 7.2 Estrutura do StateGraph por Agente

Todos os agentes compartilham a mesma topologia base:

```
perceive ──► fast_path ──► END          (se fast_path_taken = True)
perceive ──► fast_path ──► decide ──► act ──► END
                                │
                                └──► tool_node ──► decide  (loop até sem tool calls)
```

**Definição do grafo:**

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

def build_agent_graph(agent_type: str, tools: list) -> CompiledGraph:
    graph = StateGraph(AgentState)

    graph.add_node("perceive", perceive_node)
    graph.add_node("fast_path", fast_path_node)
    graph.add_node("decide", decide_node)
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_node("act", act_node)

    graph.set_entry_point("perceive")

    graph.add_edge("perceive", "fast_path")

    graph.add_conditional_edges(
        "fast_path",
        lambda state: END if state["fast_path_taken"] else "decide",
    )

    graph.add_conditional_edges(
        "decide",
        lambda state: "tool_node" if has_tool_calls(state) else "act",
    )

    graph.add_edge("tool_node", "decide")
    graph.add_edge("act", END)

    return graph.compile()
```

---

### 7.3 Responsabilidade de Cada Nó

#### `perceive`

- Recebe o `AgentState` inicial com `world_state`, `entity_id`, `trigger_event`
- Extrai o `WorldStateSlice` relevante para este agente (ex: fábrica só vê seus armazéns parceiros)
- Carrega o `decision_history` das últimas N decisões do banco
- Monta o system prompt com contexto + histórico de decisões + identidade do agente

#### `fast_path`

- Avalia regras determinísticas antes de chamar o LLM:
  - `stock[p] > HIGH_THRESHOLD` → `hold` (sem pedido)
  - `stock[p] < CRITICAL_THRESHOLD` → pedido de emergência imediato
  - `degradation >= 0.95` → recusa qualquer viagem (guardrail do engine)
- Se uma regra dispara: define `fast_path_taken = True` e `decision` diretamente
- Evita custo de token para casos óbvios

#### `decide`

- Chama `ChatOpenAI(model="gpt-4o-mini")` com as tools vinculadas via `llm.bind_tools(tools)`
- LangGraph executa o loop de tool calls automaticamente via `ToolNode`
- O LLM retorna uma decisão estruturada no formato JSON esperado pelo guardrail

#### `tool_node`

- Executa automaticamente as tool calls retornadas pelo `decide` (gerenciado pelo `ToolNode`)
- Ferramentas disponíveis por agente:

| Agente    | Tools                                     |
| --------- | ----------------------------------------- |
| Factory   | `sales_history`, `warehouse_stock_levels` |
| Warehouse | `sales_history`, `factory_stock_levels`   |
| Store     | `sales_history`, `warehouse_stock_levels` |
| Truck     | `weather`, `route_risk`                   |

#### `act`

- Recebe a decisão retornada pelo LLM
- Valida via Pydantic guardrail (ver seção 8)
- Se válida: persiste no PostgreSQL + publica em `nexus:agent_decisions`
- Se inválida: registra erro em `state["error"]` — não persiste

---

### 7.4 MasterAgent — Orquestrador

O `MasterAgent` é um grafo supervisor que **não é um agente LLM** no sentido tradicional — ele é determinístico na maioria das suas decisões e só usa o LLM para caos autônomo.

```
evaluate_world ──► dispatch_agents ──► evaluate_chaos ──► END
```

**Nó `evaluate_world`:**

- Chama `TriggerEvaluationService.evaluate_all(world_state)`
- Obtém a lista de `AgentTrigger` do tick atual

**Nó `dispatch_agents`:**

- Para cada `AgentTrigger`, cria `asyncio.create_task(agent.run_cycle(trigger))`
- Aplica `asyncio.Semaphore(MAX_AGENT_WORKERS)` para limitar concorrência OpenAI
- Fire-and-forget: o tick não aguarda conclusão dos agentes

**Nó `evaluate_chaos`:**

- Chama `ChaosService.can_inject_autonomous_event()` para exibição/log apenas
- Se pode: chama o LLM com o contexto do `WorldState` para avaliar se algum evento autônomo é plausível
- Se o LLM decidir injetar: chama `ChaosService.inject_autonomous_event()` — **este método contém o check atômico real** (ver seção 10.3); retorno `None` significa que outro evento foi injetado no mesmo tick (race condition tratada — descartar silenciosamente)

**Fluxo de passagem de estado (MasterAgent → Sub-agente):**

O MasterAgent não passa o `AgentState` diretamente para os sub-agentes. Cada sub-agente recebe apenas:

- `entity_id` — quem deve ser acordado
- `entity_type` — tipo do agente
- `trigger_event` — o evento que acordou
- `current_tick` — tick atual

O sub-agente constrói seu próprio `WorldStateSlice` via `WorldStateService` no nó `perceive`. Isso mantém os grafos desacoplados.

---

## 9. Guardrails Pydantic — Validação das Saídas dos LLMs

Nenhuma decisão de agente afeta o banco sem passar pelo schema Pydantic correspondente. Cada agente tem seu próprio arquivo em `backend/src/guardrails/`.

### `AgentDecisionBase` — `guardrails/base.py`

```python
from pydantic import BaseModel, field_validator
from typing import Literal

class AgentDecisionBase(BaseModel):
    action: str
    reasoning_summary: str          # Resumo legível da decisão (para o feed do dashboard)
```

### `FactoryDecision` — `guardrails/factory.py`

```python
class StartProductionPayload(BaseModel):
    material_id: str
    quantity_tons: float

    @field_validator("quantity_tons")
    def must_be_positive(cls, v): ...

class SendStockPayload(BaseModel):
    material_id: str
    quantity_tons: float
    destination_warehouse_id: str

    @field_validator("quantity_tons")
    def not_exceed_available_stock(cls, v, info): ...  # valida contra world_state

class FactoryDecision(AgentDecisionBase):
    action: Literal["start_production", "reduce_production", "stop_production",
                    "send_stock", "request_truck", "hold"]
    payload: StartProductionPayload | SendStockPayload | None = None
```

### `WarehouseDecision` — `guardrails/warehouse.py`

```python
class RequestResupplyPayload(BaseModel):
    material_id: str
    quantity_tons: float
    from_factory_id: str

    @field_validator("quantity_tons")
    def must_fit_available_capacity(cls, v, info): ...

class ConfirmOrderPayload(BaseModel):
    order_id: str
    quantity_tons: float
    eta_ticks: int

class RejectOrderPayload(BaseModel):
    order_id: str
    reason: str
    retry_after_ticks: int

class WarehouseDecision(AgentDecisionBase):
    action: Literal["request_resupply", "confirm_order", "reject_order",
                    "request_delivery_truck", "ration_stock", "hold"]
    payload: RequestResupplyPayload | ConfirmOrderPayload | RejectOrderPayload | None = None
```

### `StoreDecision` — `guardrails/store.py`

```python
class OrderReplenishmentPayload(BaseModel):
    material_id: str
    quantity_tons: float
    from_warehouse_id: str

    @field_validator("quantity_tons")
    def must_be_above_zero(cls, v): ...

class StoreDecision(AgentDecisionBase):
    action: Literal["order_replenishment", "order_direct_from_factory",
                    "wait_backoff", "hold"]
    payload: OrderReplenishmentPayload | None = None
```

### `TruckDecision` — `guardrails/truck.py`

```python
class AcceptContractPayload(BaseModel):
    order_id: str
    chosen_route_risk_level: Literal["low", "medium", "high"]

class RefuseContractPayload(BaseModel):
    order_id: str
    reason: Literal["high_degradation", "route_risk", "low_cargo_utilization", "in_maintenance"]

class RequestMaintenancePayload(BaseModel):
    current_degradation: float

    @field_validator("current_degradation")
    def engine_guardrail_check(cls, v):
        """Rejeita se degradation < MAINTENANCE_THRESHOLD (agente não deve pedir antes da hora)."""
        ...

class TruckDecision(AgentDecisionBase):
    action: Literal["accept_contract", "refuse_contract", "choose_route",
                    "request_maintenance", "alert_breakdown", "complete_delivery"]
    payload: AcceptContractPayload | RefuseContractPayload | RequestMaintenancePayload | None = None

    @field_validator("action")
    def degradation_guardrail(cls, v, info):
        """Se degradation >= 0.95 e action != 'request_maintenance': rejeita."""
        ...
```

### Como o guardrail é aplicado no nó `act`

```python
async def act_node(state: AgentState) -> AgentState:
    raw_decision = extract_json_from_last_message(state["messages"])

    try:
        decision = DECISION_SCHEMA_MAP[state["entity_type"]](**raw_decision)
        decision = validate_against_world_state(decision, state["world_state"])
    except ValidationError as e:
        return {**state, "error": str(e), "decision": None}

    await persist_decision(state["entity_id"], state["current_tick"], decision)
    await publisher.publish_decision(state["entity_id"], state["entity_type"], decision)

    return {**state, "decision": decision, "error": None}
```

**Hierarquia de validação:**

1. **Schema Pydantic** — tipos, obrigatoriedade, constraints básicas (ex: quantidade positiva)
2. **Validators de negócio** — verificam contra o `WorldState` atual (ex: quantidade não pode exceder estoque disponível)
3. **Guardrail do engine** — hardcoded no nó `act` e no `fast_path` (ex: `degradation >= 0.95` bloqueia viagem independente do LLM)

Se qualquer camada falhar, a decisão é descartada, o erro é logado em `agent_decisions.reasoning` e nenhum dado é persistido.

---

## 10. Mecanismos de Consistência e Concorrência

Esta seção documenta as soluções para os 5 problemas críticos de concorrência identificados na arquitetura. Cada mecanismo deve ser implementado exatamente como descrito — desvios criam race conditions silenciosas.

---

### 10.1 Reserva Atômica de Estoque (Fix: race condition stock)

**Problema:** Agentes fire-and-forget de ticks anteriores ainda rodando podem reservar o mesmo estoque de forma concorrente, porque todos leram o mesmo `WorldState` snapshot.

**Solução:** A coluna `stock_reserved` em `factory_products` e `warehouse_stocks` permite reservas atômicas via SQL sem locks de aplicação:

```sql
-- Reserva atômica — falha silenciosa se estoque insuficiente
UPDATE warehouse_stocks
SET stock_reserved = stock_reserved + :qty
WHERE warehouse_id = :wid AND material_id = :mid
  AND (stock - stock_reserved) >= :qty
RETURNING *;
-- Se 0 rows afetadas: estoque disponível insuficiente
```

**Regras:**
- `stock_reserved` é incrementado em `confirm_order` e decrementado em `mark_delivered` e em cancelamentos
- O estoque **disponível real** para novos pedidos é sempre `stock - stock_reserved`, nunca `stock` sozinho
- `WarehouseService.confirm_order()` retorna `None` se o UPDATE retornar 0 rows — o agente deve tratar como rejeição
- Em `produce_factory_stocks()`, a produção incrementa `stock`, nunca `stock_reserved`

---

### 10.2 Anti-Deadlock Fábrica/Armazém (Fix: circular dependency)

**Problema:** Fábrica para produção quando todos parceiros >80%. Armazém esvazia abaixo de `min_stock` e solicita reabastecimento. Fábrica recusa porque parceiros ainda >80%. Deadlock.

**Solução:** A regra de fallback tem uma exceção explícita:

> A fábrica só aplica a regra de parada/redução por 80% se **não houver `pending_order` com status `pending` ou `confirmed` direcionado a ela** de qualquer armazém parceiro. Um pedido ativo de um parceiro sobrepõe a regra de 80% para aquele produto específico.

**Implementação no `fast_path` da fábrica:**

```python
# fast_path_node para fábrica
for material_id in factory.products:
    all_partners_over_80 = all(
        warehouse_stock_pct(w, material_id) > 0.80
        for w in partner_warehouses
    )
    has_urgent_resupply = any(
        o.target_id == factory.id and o.material_id == material_id
        and o.status in ("pending", "confirmed")
        for o in world_state.pending_orders
    )
    if all_partners_over_80 and not has_urgent_resupply:
        # fast_path: parar produção deste produto
        ...
    # caso contrário: escala para LLM ou mantém produção
```

---

### 10.3 Injeção Atômica de Caos (Fix: cooldown race)

**Problema:** Múltiplas tasks assíncronas podem verificar `can_inject_autonomous_event()` simultaneamente e todas passarem pelo cooldown, resultando em 2+ eventos autônomos ativos.

**Solução:** `inject_autonomous_event()` usa `SELECT FOR UPDATE` dentro de uma transação:

```python
async def inject_autonomous_event(data: ChaosEventCreate) -> ChaosEvent | None:
    async with session.begin():
        # Lock exclusivo — bloqueia outras transactions no mesmo SELECT
        row = await session.execute(
            select(func.count(ChaosEventModel.id))
            .where(ChaosEventModel.status == "active")
            .with_for_update()
        )
        active_count = row.scalar()
        last_tick = await event_repo.get_last_resolved_autonomous_tick()

        if active_count > 0:
            return None  # já há evento ativo
        if last_tick and (current_tick - last_tick) < 24:
            return None  # cooldown não passou

        return await event_repo.create({**data, "source": "master_agent"})
```

**Regra:** `can_inject_autonomous_event()` continua existindo mas é somente-leitura — para exibição no dashboard. **Nunca** chamar como guarda antes de `inject_autonomous_event()` — a verificação real acontece dentro do lock.

---

### 10.4 Deleção de Entidades com Pedidos Pendentes (Fix: orphaned orders)

**Problema:** Deletar fábrica/armazém/loja deixa `pending_orders` apontando para entidade inexistente. Agentes solicitantes ficam bloqueados esperando resposta que nunca virá.

**Solução:** Cascade controlado na deleção, com distinção entre pedidos "em trânsito" e "apenas aguardando":

#### Regras por status do pedido no momento da deleção:

| Status do pedido | Há caminhão com rota ativa? | Ação                                                              |
| ---------------- | --------------------------- | ----------------------------------------------------------------- |
| `pending`        | Não                         | Cancelar (`status = 'cancelled'`, `cancellation_reason = 'target_deleted'`) |
| `confirmed`      | Não                         | Cancelar — reserva de estoque é liberada (`stock_reserved -= qty`) |
| `confirmed`      | Sim (caminhão em rota)      | **Manter** — caminhão completa entrega normalmente               |
| `rejected`       | —                           | Ignorar — já resolvido                                            |
| `delivered`      | —                           | Ignorar — já resolvido                                            |

#### Comportamento do caminhão ao chegar em entidade deletada:

Quando um caminhão completa uma rota para um destino que não existe mais:
1. `truck_arrived` event é disparado normalmente pelo engine
2. O agente do caminhão verifica que `dest_id` não existe mais
3. Caminhão descarrega a carga (estoque é creditado a ninguém — carga é perdida no mundo)
4. Caminhão retorna ao status `idle` na posição do destino original
5. Evento `cargo_lost_at_deleted_entity` publicado no canal `nexus:events` (visível no dashboard)

#### Trigger para agentes com pedidos cancelados:

`TriggerEvaluationService` deve incluir:

```python
# Acordar agentes cujos pedidos foram cancelados por deleção
cancelled_orders = [
    o for o in world_state.pending_orders
    if o.status == "cancelled"
    and o.cancellation_reason == "target_deleted"
    and o.requester_id == entity.id
]
if cancelled_orders:
    triggers.append(AgentTrigger(
        entity_id=entity.id,
        event_type="order_cancelled_target_deleted",
        payload={"cancelled_order_ids": [str(o.id) for o in cancelled_orders]}
    ))
```

---

### 10.5 Lock de Avaliação de Contrato para Caminhões (Fix: truck multiple contracts)

**Problema:** N fábricas enviam `contract_proposal` para o mesmo caminhão idle. N tasks são criadas via `asyncio.create_task`. Todas veem o caminhão como `idle` no snapshot e todas podem retornar `accept`.

**Solução:** Status intermediário `evaluating` + transição atômica via SQL:

```python
# Antes de criar a task do agente do caminhão
locked = await truck_repo.try_lock_for_evaluation(truck_id)
if not locked:
    # Caminhão já está sendo avaliado por outra proposta — ignorar este ciclo
    return

# Só uma task chega aqui por caminhão
await asyncio.create_task(truck_agent.run_cycle(trigger))
```

**`try_lock_for_evaluation` no repositório:**

```python
async def try_lock_for_evaluation(self, truck_id: str) -> bool:
    result = await self.session.execute(
        update(TruckModel)
        .where(TruckModel.id == truck_id, TruckModel.status == "idle")
        .values(status="evaluating")
        .returning(TruckModel.id)
    )
    return result.rowcount > 0
```

**Fluxo no agente:**
- Se o agente aceita: `status → in_transit`
- Se o agente recusa: `status → idle` (libera para próxima proposta)
- Se o agente falha/timeout: `status → idle` (rollback no finally block)

**Visibilidade:** Status `evaluating` é transitório — o `WorldStatePayload` pode filtrar ou exibir como `idle` no dashboard para simplificar a UX.

---

## 11. Convenções Gerais

- Todo o código em **inglês** (variáveis, funções, classes, commits)
- Nomes expressivos e autoexplicativos — sem docstrings, sem comentários redundantes
- **TDD obrigatório** — teste antes da implementação, sem exceções
- Agentes testáveis com `WorldState` mockado e `FakeListChatModel` do LangChain no lugar do `ChatOpenAI`
- `WorldState` carregado em uma query com joins — sem N+1
- Nenhuma decisão de agente afeta o banco sem passar pelo guardrail Pydantic
