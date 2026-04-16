# Nexus Twin - Arquitetura Base

## 1. Visão Geral

Simulação de um **mundo fechado e autônomo** de cadeia de suprimentos, inspirado na dinâmica de NPCs de um RPG. Cada entidade do mundo — Fábrica, Armazém, Loja, Caminhão — é um agente de IA com objetivos próprios, percepção do estado do mundo e capacidade de se comunicar com outros agentes para resolver seus problemas **sem intervenção humana**.

**Domínio:** O mundo é o estado de São Paulo, com rodovias reais do OSM. Fábricas produzem e distribuem, Armazéns redistribuem regionalmente, Lojas vendem e repõem estoque, Caminhões transportam e reagem a imprevistos. Os agentes se comunicam por eventos assíncronos — uma loja com estoque baixo aciona o armazém, que aciona a fábrica, que aciona o caminhão — tudo de forma encadeada e autônoma.

**Stack de IA:** Cada agente é um `StateGraph` do **LangGraph** rodando ciclos `perceive → decide → act`. O LLM usado é `gpt-4o-mini` (OpenAI). Todas as decisões são validadas por schemas Pydantic antes de afetar o banco de dados.

**Papel do usuário:** Game master — monitora o ecossistema via dashboard em tempo real, pode injetar eventos de caos e moldar o mundo criando ou removendo entidades (fábricas, armazéns, lojas, caminhões). Os agentes reagem às mudanças automaticamente no próximo tick.

---

## 2. Stack Tecnológico

### Backend

| Camada        | Tecnologia                                          |
| ------------- | --------------------------------------------------- |
| Runtime       | Python 3.11+                                        |
| Framework     | FastAPI                                             |
| IA / Agentes  | OpenAI API (`gpt-4o-mini`) via LangGraph            |
| Orquestração  | LangGraph — `StateGraph` por agente (ciclo cíclico) |
| Tools         | LangGraph ToolNode + funções Python puras           |
| Validação     | Pydantic v2 (guardrails de decisões)                |
| Database      | PostgreSQL 15+ (estado persistente do mundo)        |
| Message Queue | Celery + Redis (jobs assíncronos dos agentes)       |
| Realtime      | FastAPI WebSockets + Redis Pub/Sub                  |
| Logging       | Loguru                                              |

### Frontend (Game-like Dashboard)

| Camada        | Tecnologia                                                      |
| ------------- | --------------------------------------------------------------- |
| Framework     | React 18+ / TypeScript                                          |
| Mapa / WebGL  | MapLibre GL JS 4+ (renderização do mapa base)                   |
| Visualização  | deck.gl 9+ sobreposto ao MapLibre                               |
| Animação      | `TripsLayer` (caminhões em movimento), `ScatterplotLayer` (nós) |
| Estado Global | Zustand (WorldState sincronizado via WebSocket)                 |
| Realtime      | WebSocket nativo (FastAPI backend)                              |
| UI / HUD      | Tailwind CSS + shadcn/ui (painéis de inspeção)                  |

### Geo Infrastructure (Self-Hosted)

| Componente        | Tecnologia                                               |
| ----------------- | -------------------------------------------------------- |
| Dados OSM         | Geofabrik — extract Sudeste Brasil (`.osm.pbf`, ~800 MB) |
| Geração de Tiles  | Planetiler → PMTiles (formato de tile vetorial compacto) |
| Servidor de Tiles | Martin (Rust) — serve PMTiles + PostGIS via HTTP         |
| Roteamento        | Valhalla (Docker) — rotas reais por rodovias do OSM      |
| Geo Database      | PostgreSQL + PostGIS — rotas, posições, entidades        |

### Infrastructure

- **Containerização:** Docker + Docker Compose (toda a geo stack inclusa)
- **Environment:** `.env` para config local/prod

---

## 3. Estrutura de Pastas

```
nexus-twin/
├── backend/
│   ├── src/
│   │   ├── world/                      # Nexus Twin — estado do mundo físico
│   │   │   ├── __init__.py
│   │   │   ├── state.py                # WorldState: snapshot imutável do mundo
│   │   │   ├── entities/               # Modelos de domínio
│   │   │   │   ├── material.py         # Material (catálogo dinâmico — id, name, is_active)
│   │   │   │   ├── factory.py          # Fábrica (products: List[material_id], capacidade, produção, status)
│   │   │   │   ├── warehouse.py        # Armazém (stock: Dict[material_id, qty], capacidade, localização)
│   │   │   │   ├── store.py            # Loja (stock/demand/reorder_point: Dict[material_id, qty])
│   │   │   │   └── truck.py            # Caminhão (carga, rota, posição, degradação, truck_type)
│   │   │   └── physics.py              # Cálculos determinísticos (distância, ETAs, degradação)
│   │   │
│   │   ├── agents/                     # Multi-Agent System (MAS) — LangGraph
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # AgentState (TypedDict) + builder de StateGraph base
│   │   │   ├── factory_agent.py        # StateGraph: perceive → decide → act (produção)
│   │   │   ├── warehouse_agent.py      # StateGraph: perceive → decide → act (estoque)
│   │   │   ├── store_agent.py          # StateGraph: perceive → decide → act (reposição de loja)
│   │   │   ├── truck_agent.py          # StateGraph: perceive → decide → act (rota/contrato)
│   │   │   ├── master_agent.py         # Grafo supervisor: roteia WorldState para sub-agentes
│   │   │   └── prompts/                # System prompts por agente (isolados da lógica do grafo)
│   │   │       ├── factory.md
│   │   │       ├── warehouse.md
│   │   │       ├── store.md
│   │   │       └── truck.md
│   │   │
│   │   ├── tools/                      # Ferramentas dos agentes (LangGraph ToolNode)
│   │   │   ├── __init__.py
│   │   │   ├── weather.py              # @tool — consulta clima para decisão de rota
│   │   │   ├── route_risk.py           # @tool — avalia risco de segmento (bloqueios, tráfego, histórico)
│   │   │   └── sales_history.py        # @tool — histórico de vendas para previsão de produção
│   │   │
│   │   ├── simulation/                 # Engine de simulação
│   │   │   ├── __init__.py
│   │   │   ├── engine.py               # Loop de ticks — chama publisher após apply_physics
│   │   │   ├── events.py               # Definição dos tipos de evento + roteamento entre agentes
│   │   │   ├── publisher.py            # Redis Pub/Sub: publica WorldState e decisões nos canais
│   │   │   └── chaos.py                # Injeção de eventos disruptivos
│   │   │
│   │   ├── workers/                    # Celery — jobs background não-LLM
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py           # Instância Celery (broker=Redis, backend=Redis)
│   │   │   └── tasks/
│   │   │       ├── __init__.py
│   │   │       ├── reports.py          # @shared_task — relatórios de eficiência da simulação
│   │   │       └── exports.py          # @shared_task — exportação de histórico de decisões
│   │   │
│   │   ├── guardrails/                 # Validação de decisões dos agentes — um arquivo por tipo de agente
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # AgentDecisionBase + utilitários de validação compartilhados
│   │   │   ├── factory.py              # FactoryDecision, StartProductionPayload, SendStockPayload
│   │   │   ├── warehouse.py            # WarehouseDecision, RequestResupplyPayload, ConfirmOrderPayload
│   │   │   ├── store.py                # StoreDecision, OrderReplenishmentPayload
│   │   │   └── truck.py                # TruckDecision, AcceptContractPayload, RefuseContractPayload
│   │   │
│   │   ├── services/                   # Camada de negócio — um arquivo por domínio
│   │   │   ├── __init__.py
│   │   │   ├── simulation.py           # SimulationService — ciclo de vida do loop de ticks
│   │   │   ├── world_state.py          # WorldStateService — carrega e serializa o WorldState
│   │   │   ├── material.py             # MaterialService — CRUD do catálogo de materiais
│   │   │   ├── factory.py              # FactoryService — CRUD + ajuste de estoque de fábricas
│   │   │   ├── warehouse.py            # WarehouseService — CRUD + confirmação/rejeição de pedidos
│   │   │   ├── store.py                # StoreService — CRUD + criação de pedidos de reposição
│   │   │   ├── truck.py                # TruckService — CRUD + atribuição de rotas e manutenção
│   │   │   ├── chaos.py                # ChaosService — injeção e resolução de eventos de caos
│   │   │   ├── order.py                # OrderService — ciclo de vida dos pending_orders
│   │   │   ├── route.py                # RouteService — integração Valhalla + persistência de rotas
│   │   │   ├── physics.py              # PhysicsService — cálculos determinísticos por tick
│   │   │   └── trigger_evaluation.py   # TriggerEvaluationService — avalia gatilhos dos agentes por tick
│   │   │
│   │   ├── repositories/               # Acesso ao banco — um arquivo por entidade/agregado
│   │   │   ├── __init__.py
│   │   │   ├── material.py             # MaterialRepository — queries de materiais
│   │   │   ├── factory.py              # FactoryRepository — queries de fábricas + factory_products
│   │   │   ├── warehouse.py            # WarehouseRepository — queries de armazéns + warehouse_stocks
│   │   │   ├── store.py                # StoreRepository — queries de lojas + store_stocks
│   │   │   ├── truck.py                # TruckRepository — queries de caminhões
│   │   │   ├── route.py                # RouteRepository — queries de rotas (PostGIS)
│   │   │   ├── order.py                # OrderRepository — queries de pending_orders
│   │   │   ├── event.py                # EventRepository — queries de eventos de caos
│   │   │   └── agent_decision.py       # AgentDecisionRepository — queries de decisões dos agentes
│   │   │
│   │   ├── database/                   # Persistência
│   │   │   ├── __init__.py
│   │   │   ├── session.py              # AsyncSession factory (asyncpg) + get_db dependency
│   │   │   ├── models/                 # SQLAlchemy ORM models — um arquivo por entidade/tabela
│   │   │   │   ├── __init__.py
│   │   │   │   ├── material.py         # Material
│   │   │   │   ├── factory.py          # Factory, FactoryProduct, FactoryPartnerWarehouse
│   │   │   │   ├── warehouse.py        # Warehouse, WarehouseStock
│   │   │   │   ├── store.py            # Store, StoreStock
│   │   │   │   ├── truck.py            # Truck
│   │   │   │   ├── route.py            # Route
│   │   │   │   ├── order.py            # PendingOrder
│   │   │   │   ├── event.py            # ChaosEvent
│   │   │   │   └── agent_decision.py   # AgentDecision
│   │   │   ├── seed.py                 # Mundo padrão: dados iniciais fixos (PRD seção 3)
│   │   │   └── migrations/             # Alembic migrations
│   │   │
│   │   ├── api/                        # HTTP + WebSocket endpoints
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py         # Dependency factories (get_<service>) para FastAPI Depends
│   │   │   ├── models/                 # Pydantic schemas de request/response — um arquivo por domínio
│   │   │   │   ├── __init__.py
│   │   │   │   ├── common.py           # StockAdjust (compartilhado entre factories, warehouses, stores)
│   │   │   │   ├── simulation.py       # SpeedUpdate
│   │   │   │   ├── materials.py        # MaterialCreate, MaterialUpdate, MaterialResponse
│   │   │   │   ├── factories.py        # FactoryResponse
│   │   │   │   ├── warehouses.py       # WarehouseResponse
│   │   │   │   ├── stores.py           # StoreResponse
│   │   │   │   ├── trucks.py           # TruckResponse
│   │   │   │   ├── chaos.py            # ChaosEventCreate, ChaosEventResponse
│   │   │   │   └── decisions.py        # DecisionResponse
│   │   │   ├── routes/
│   │   │   │   ├── simulation.py       # Controle da simulação (start/stop/tick, velocidade)
│   │   │   │   ├── world.py            # Leitura do estado do mundo (snapshot, entidades)
│   │   │   │   ├── materials.py        # CRUD do catálogo de materiais
│   │   │   │   ├── factories.py        # CRUD de fábricas + ajuste de estoque
│   │   │   │   ├── warehouses.py       # CRUD de armazéns + ajuste de estoque
│   │   │   │   ├── stores.py           # CRUD de lojas + ajuste de estoque
│   │   │   │   ├── trucks.py           # CRUD de caminhões
│   │   │   │   ├── decisions.py        # Leitura do histórico de decisões dos agentes
│   │   │   │   └── chaos.py            # Injeção manual de eventos disruptivos
│   │   │   └── websocket.py            # Streaming de eventos para o dashboard
│   │   │
│   │   ├── enums/                      # Enums compartilhados entre todas as camadas
│   │   │   ├── __init__.py             # Re-exporta todas as classes
│   │   │   ├── agents.py               # AgentType
│   │   │   ├── trucks.py               # TruckType, TruckStatus
│   │   │   ├── facilities.py           # FactoryStatus, WarehouseStatus, StoreStatus
│   │   │   ├── routes.py               # RouteNodeType, RouteStatus
│   │   │   ├── events.py               # ChaosEventSource, ChaosEventEntityType, ChaosEventStatus
│   │   │   └── orders.py               # OrderStatus, OrderRequesterType, OrderTargetType
│   │   │
│   │   └── main.py                     # Entry point FastAPI
│   │
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── .env.example
│   ├── pyproject.toml
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── map/                        # Camada de visualização WebGL (deck.gl)
│   │   │   ├── WorldMap.tsx            # Canvas principal: mapa + todas as layers
│   │   │   ├── layers/
│   │   │   │   ├── TrucksLayer.ts      # TripsLayer animado — posição interpolada por timestamp
│   │   │   │   ├── NodesLayer.ts       # ScatterplotLayer — fábricas/armazéns/lojas, raio = estoque
│   │   │   │   ├── RoutesLayer.ts      # PathLayer — rotas com cor por status (ok/tráfego/bloqueada)
│   │   │   │   └── EventsLayer.ts      # IconLayer — ícones de eventos de caos (explosão, chuva)
│   │   │   └── mapConfig.ts            # Viewport inicial, estilos do mapa base
│   │   │
│   │   ├── hud/                        # UI sobreposta ao mapa (HUD)
│   │   │   ├── InspectPanel.tsx        # Painel lateral ao clicar em caminhão ou nó
│   │   │   ├── AgentLog.tsx            # Feed rolante de decisões dos agentes
│   │   │   ├── ChaosPanel.tsx          # Botões para injetar eventos disruptivos
│   │   │   ├── WorldManagement.tsx     # Criar/remover entidades (fábrica, armazém, loja, caminhão)
│   │   │   └── StatsBar.tsx            # Barra superior: eficiência global, alertas ativos
│   │   │
│   │   ├── store/
│   │   │   └── worldStore.ts           # Zustand: WorldState sincronizado via WebSocket
│   │   │
│   │   ├── hooks/
│   │   │   ├── useWorldSocket.ts       # Conecta WebSocket, atualiza store a cada tick
│   │   │   └── useInspect.ts           # Estado de seleção (caminhão ou nó clicado)
│   │   │
│   │   ├── types/
│   │   │   └── world.ts                # Tipos TypeScript compartilhados (WorldState, Entity, TruckType, Event)
│   │   │
│   │   ├── lib/
│   │   │   └── geo.ts                  # Helpers GeoJSON (interpolação de posição, rotas)
│   │   │
│   │   └── App.tsx                     # Layout: WorldMap fullscreen + HUD overlay
│   ├── package.json
│   └── tsconfig.json
│
├── geo/
│   └── data/                           # Arquivos grandes — não versionados no git
│       ├── sudeste-latest.osm.pbf      # Extract OSM do Sudeste (Geofabrik, ~800 MB)
│       ├── sudeste.pmtiles             # Tiles vetoriais gerados pelo Planetiler (~2–4 GB)
│       └── valhalla_tiles/             # Grafo de roteamento gerado pelo Valhalla
│
├── .specs/                             # Documentação de produto e design
├── docker-compose.yml
├── CLAUDE.md
└── README.md
```

---

## 4. Decisões Arquiteturais

### 4.1 Nexus Twin (World State)

- **Snapshot imutável:** `WorldState` é reconstruído a cada tick — agentes nunca mutam o estado diretamente.
- **Física determinística:** `physics.py` calcula distâncias, ETAs e degradação de caminhões com fórmulas fixas (sem IA). Não há simulação de combustível — o único trade-off dos caminhões é tempo vs. risco de rota.
- **Materiais como catálogo:** `stock`, `demand_rate`, `production_rate_max`, `reorder_point` e similares são sempre `Dict[material_id, quantidade]` — nunca strings hardcoded. O catálogo de materiais é carregado junto com o `WorldState`.
- **Degradação de caminhões:** A cada viagem, `degradation` aumenta proporcionalmente à distância e ao peso transportado. `breakdown_risk` cresce exponencialmente acima de 70% de degradação. Guardrail do engine: `degradation ≥ 95%` bloqueia qualquer viagem independente da decisão do agente. Manutenção zera `degradation` mas imobiliza o caminhão por 2–24 ticks proporcional ao nível de desgaste.
- **Fonte única de verdade:** PostgreSQL persiste o estado; Redis é apenas cache/pub-sub.

### 4.2 Multi-Agent System (MAS) — LangGraph

Cada agente é um `StateGraph` compilado com três nós fixos:

```
perceive ──► decide ──► act ──► END
               │
               └──► tool_node ──► decide  (loop até sem tool calls)
```

- **`AgentState` (TypedDict):** Estado compartilhado dentro do grafo — `world_state`, `messages`, `decision`, `memory` (últimas N decisões).
- **Nó `perceive`:** Extrai o slice relevante do `WorldState` para aquele agente e monta o contexto inicial.
- **Nó `decide`:** Chama `ChatOpenAI(model="gpt-4o-mini")` com as tools vinculadas. LangGraph executa o loop de tool calls automaticamente via `ToolNode`.
- **Nó `act`:** Valida a decisão via Pydantic (`guardrails/<agent_type>.py`) e persiste no PostgreSQL via repository.
- **`MasterAgent`:** Grafo supervisor que avalia eventos pendentes a cada tick e despacha apenas os agentes que têm eventos relevantes — **fire-and-forget**, sem bloquear o tick.
- **Memória por agente:** Histórico de decisões passadas injetado no system prompt a cada ciclo.
- **Paralelismo:** Agentes despachados rodam em background via `asyncio.create_task`; o tick não aguarda conclusão. Sem Celery para as chamadas LLM.
- **Dois perfis de caminhão:**
  - `proprietario` — vinculado a uma fábrica; executa ordens diretas, sem autonomia para recusar.
  - `terceiro` — agente self-interested; avalia propostas de contratação com base em risco de rota, distância, aproveitamento de carga (≥ 80%) e `degradation` atual; pode recusar e comunica o motivo. Pedidos com `age_ticks` alto elevam prioridade para evitar deadlocks logísticos.

### 4.3 Tools dos Agentes

- Ferramentas definidas com o decorator `@tool` do LangChain/LangGraph em `tools/`.
- Stateless — recebem parâmetros tipados, retornam Pydantic models.
- Vinculadas ao LLM via `llm.bind_tools([weather, sales_history])`.
- `ToolNode` no grafo executa automaticamente as tool calls retornadas pelo LLM.

### 4.4 Simulação & Caos

- **Tick mínimo: 10 segundos.** Um tick avança 1 hora simulada. A velocidade pode ser ajustada pelo usuário (mínimo 10s real).
- **Physics tick ≠ Agent cycle:** O engine atualiza posições, estoques e timestamps a cada tick (operação síncrona e barata, sem IA). Agentes LLM são disparados de forma assíncrona e não bloqueiam o tick.
- **Fire-and-forget:** O tick termina após aplicar física e publicar eventos. Agentes rodam em background via `asyncio.create_task`; a decisão é aplicada no próximo estado disponível.
- **Caminhões em trânsito — sem LLM:** Caminhões com rota ativa e sem eventos pendentes não acordam o agente. O LLM só é chamado em eventos: `route_blocked`, `truck_arrived`, `truck_breakdown`, `new_order` (proprietário), `contract_proposal` (terceiro).
- **Gatilhos preditivos para loja/armazém/fábrica:** O engine avalia a cada tick, para cada produto `p`: `(stock[p] - min_stock[p]) / demand_rate[p] < lead_time_ticks × 1.5`. O agente acorda quando a projeção indica que o estoque vai cruzar o nível mínimo (`reorder_point` para lojas, `min_stock` para armazéns) antes da reposição chegar — não quando o nível é efetivamente cruzado.
- **Fast path determinístico:** Antes de chamar o LLM, o agente verifica regras simples (stock > HIGH_THRESHOLD → hold; stock < CRITICAL → pedido de emergência). Só chega ao LLM quando está na zona de ambiguidade.
- **Caos controlado:** `chaos.py` expõe uma interface para injetar eventos disruptivos: greve de caminhoneiros, quebra de máquina na fábrica, pico de demanda, bloqueio de rodovia, tempestade regional, caminhão quebrado em rota e demanda zero repentina. O `MasterAgent` pode acionar autonomamente um subconjunto desses eventos quando detecta condições sistêmicas (ex: fábrica em produção máxima por ≥ 12 ticks). Regras: máximo 1 evento autônomo por vez, cooldown mínimo de 24 ticks após resolução do evento anterior, sem empilhamento. Greve, bloqueio de rodovia, tempestade e demanda zero são exclusivamente manuais (usuário).
- **Catálogo de materiais:** Entidade independente gerenciada pelo usuário via dashboard — `id`, `name`, `is_active`. Todos os materiais são medidos em toneladas, garantindo que `capacity_tons` dos caminhões seja comparável diretamente com qualquer produto sem conversão. Fábricas, armazéns e lojas referenciam materiais pelo `id` do catálogo. No frontend, qualquer campo de seleção de material usa um combo com os materiais ativos no catálogo.
- **Mundo padrão (seed):** O sistema inicia com um mundo pré-populado — catálogo com 3 materiais (`tijolos`, `vergalhao`, `cimento`), 3 fábricas (Campinas, Sorocaba, Votorantim), 3 armazéns (Ribeirão Preto, Jundiaí, Mogi das Cruzes), 5 lojas (SP capital + região) e 6 caminhões (3 proprietários + 3 terceiros).
- **Sem Celery para LLM:** O paralelismo de agentes é feito via `asyncio.create_task` diretamente no engine. Celery permanece apenas para jobs de background não-LLM (ex: gerar relatórios, exportar dados).

### 4.5 Redis Pub/Sub & Celery

#### Pub/Sub — `simulation/publisher.py`

Responsável por publicar nos canais Redis. É chamado em dois momentos distintos:

1. **Pelo engine** — ao fim de cada tick, após `apply_physics()`
2. **Pelos agentes** — ao persistir uma decisão (resultado do fire-and-forget)

| Canal Redis             | Publicado por             | Consumido por      | Conteúdo                                  |
| ----------------------- | ------------------------- | ------------------ | ----------------------------------------- |
| `nexus:world_state`     | `engine.py` (a cada tick) | `api/websocket.py` | Snapshot completo do WorldState           |
| `nexus:agent_decisions` | agentes (fire-and-forget) | `api/websocket.py` | Decisão individual + agente + timestamp   |
| `nexus:events`          | `engine.py` + `chaos.py`  | `api/websocket.py` | Eventos de caos, alertas, triggers ativos |

`api/websocket.py` é o subscriber — assina os três canais e faz o forward para os clientes WebSocket conectados ao dashboard.

#### Celery — `workers/`

Exclusivo para jobs background **não-LLM**. O paralelismo de agentes LLM usa `asyncio.create_task` — Celery não entra nesse fluxo.

- `workers/celery_app.py` — instância Celery com `broker=REDIS_URL` e `backend=REDIS_URL`. Processo separado do FastAPI (`celery -A src.workers.celery_app worker`).
- `workers/tasks/reports.py` — `@shared_task` para geração de relatórios de eficiência (acionado via endpoint REST ou agendado).
- `workers/tasks/exports.py` — `@shared_task` para exportação de histórico de decisões e eventos.

### 4.6 API & Realtime

- **REST:** Controle da simulação e leitura de estado.
- **WebSocket:** `api/websocket.py` assina os canais Redis e faz streaming para o dashboard (decisões, alertas, WorldState por tick).
- **Rate Limiting:** `asyncio.Semaphore(MAX_AGENT_WORKERS)` controla concorrência de chamadas à OpenAI API.

### 4.7 Frontend — Visualização Game-like

- **Fullscreen WebGL:** `WorldMap.tsx` ocupa 100% da tela; HUD é overlay com `pointer-events` seletivo.
- **Animação de caminhões:** `TripsLayer` recebe array de `{path: [[lng,lat],...], timestamps: [ms,...]}` por caminhão. O frontend interpola a posição com base no `currentTime` do tick — sem recalcular posição no servidor a cada frame.
- **Nós vivos:** Raio do `ScatterplotLayer` de cada fábrica/armazém é proporcional ao nível de estoque atual. Cor muda para vermelho em nível crítico.
- **Rotas com status:** `RoutesLayer` colore cada segmento por status — verde (livre), amarelo (tráfego), vermelho (bloqueada por evento de caos).
- **Interação por clique:** `onClick` no deck.gl identifica o objeto (caminhão ou nó). `useInspect` abre o `InspectPanel` com os dados daquela entidade.
- **Estado global Zustand:** `worldStore` recebe o `WorldState` completo a cada tick via WebSocket e distribui para as layers sem prop drilling.
- **Sem Streamlit:** Descartado — não suporta animação WebGL em tempo real nem clique em objetos do mapa.

### 4.8 Pipeline Geo — Mapa Real de São Paulo

O mapa e o roteamento são 100% self-hosted, sem dependência de API paga em produção.

#### Setup único (one-time)

```
1. Download OSM data
   └── geofabrik.de → sudeste-latest.osm.pbf (~800 MB)
       (cobre SP, RJ, MG, ES — filtrar SP no Planetiler se necessário)

2. Gerar tiles vetoriais
   └── Planetiler --osm-path=sudeste.osm.pbf --output=sudeste.pmtiles
       (~30 min, resultado: ~2–4 GB PMTiles com ruas, rodovias, labels)

3. Preparar dados de roteamento
   └── Valhalla build_tiles --config valhalla.json sudeste.osm.pbf
       (~20 min, gera grafo de roteamento específico para caminhões)
```

#### Runtime (Docker Compose)

```
martin           → serve sudeste.pmtiles como vector tiles HTTP
                   MapLibre GL JS consome: http://localhost:3000/tiles/{z}/{x}/{y}

valhalla         → HTTP API de roteamento
                   POST /route {"locations": [A, B], "costing": "truck"}
                   Retorna: polyline com waypoints reais pelas rodovias (ex: Anhanguera, Bandeirantes)

backend          → antes de iniciar cada viagem de caminhão:
                   1. Chama Valhalla para obter rota real (lat/lng waypoints)
                   2. Calcula timestamps por waypoint (distância / velocidade média)
                   3. Persiste {truck_id, path: [...], timestamps: [...]} no PostGIS
                   4. Envia via WebSocket para o frontend

frontend         → TripsLayer anima o caminhão ao longo do path com os timestamps
                   (interpolação suave entre waypoints, 60fps)
```

#### Localidades fictícias no mapa real

- Fábricas, armazéns e lojas recebem coordenadas reais (lat/lng de cidades paulistas).
- Exemplo: Fábrica em Campinas, Armazém em Ribeirão Preto, Loja em São Paulo capital.
- Rotas entre eles seguem as rodovias reais do OSM (Anhanguera SP-330, Bandeirantes SP-348, Dutra BR-116, Castelo Branco SP-280, etc.).

---

## 5. Dependências Python

```toml
[project]
requires-python = ">=3.11"

[project.dependencies]
fastapi = ">=0.111"
uvicorn = { extras = ["standard"] }
openai = ">=1.30"             # OpenAI API (gpt-4o-mini)
langgraph = ">=0.2"           # Orquestração dos agentes (StateGraph)
langchain-openai = ">=0.1"    # ChatOpenAI + bind_tools
langchain-core = ">=0.2"      # @tool decorator, ToolNode, mensagens
pydantic = ">=2.0"            # Guardrails / validação
sqlalchemy = ">=2.0"          # ORM
alembic = ">=1.13"            # Migrations
asyncpg = ">=0.29"            # Driver async PostgreSQL
celery = { extras = ["redis"] }  # Jobs background (não-LLM)
redis = ">=5.0"
loguru = ">=0.7"
httpx = ">=0.27"              # HTTP client para ferramentas externas

[project.optional-dependencies]
test = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "testcontainers[postgres]>=4.0",  # Banco PostgreSQL efêmero para testes de integração
]
```

### Dependências Frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "deck.gl": "^9",
    "@deck.gl/geo-layers": "^9",
    "@deck.gl/layers": "^9",
    "maplibre-gl": "^4",
    "zustand": "^4",
    "@shadcn/ui": "latest",
    "tailwindcss": "^3"
  },
  "devDependencies": {
    "typescript": "^5",
    "vite": "^5",
    "@types/react": "^18"
  }
}
```

> **MapLibre GL** é open-source (sem API key obrigatória). Tiles servidos pelo Martin self-hosted a partir do PMTiles gerado pelo Planetiler.

---

## 6. Variáveis de Ambiente

```dotenv
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Database (PostGIS)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/nexus_twin

# Redis
REDIS_URL=redis://localhost:6379

# API
API_PORT=8000
API_HOST=0.0.0.0

# Frontend
VITE_API_URL=http://localhost:8000
VITE_TILE_SERVER_URL=http://localhost:3001   # Martin tile server

# Simulation
TICK_INTERVAL_SECONDS=10           # mínimo — ajustável pelo usuário no dashboard
MAX_AGENT_WORKERS=4                          # asyncio.Semaphore — concorrência de chamadas à OpenAI

# Geo / Roteamento
VALHALLA_URL=http://localhost:8002           # Valhalla routing engine
OSM_DATA_PATH=./geo/data/sudeste-latest.osm.pbf
PMTILES_PATH=./geo/data/sudeste.pmtiles
```

---

## 7. Fluxo de uma Decisão (End-to-End)

```
Tick N  (10s real = 1h simulada)
  │
  ├── engine.py lê WorldState do PostgreSQL
  │
  ├── apply_physics()  — síncrono, sem IA
  │       └── Atualiza posições de caminhões, decrementa estoques, avança tempo
  │
  ├── evaluate_triggers()  — determinístico, sem IA
  │       ├── Caminhões: tem evento pendente (route_blocked, arrived, breakdown)?
  │       └── Loja/Armazém/Fábrica: ticks_to_empty < replenishment_ticks × SAFETY_FACTOR?
  │
  ├── Para cada agente com gatilho ativo:
  │       └── asyncio.create_task(agent.run_cycle(event))  ← fire-and-forget
  │
  ├── Publica WorldState via Redis → WebSocket → Dashboard
  │
  └── Tick N+1  (engine não aguarda conclusão dos agentes)

  ... (assíncrono, em background)
  ├── [warehouse_agent] perceive()
  │       └── Projeta: ticks_to_empty=4, replenishment_ticks=6 — acorda com antecedência
  │
  ├── [warehouse_agent] fast_path()
  │       └── Zona de ambiguidade → escala para LLM
  │
  ├── [warehouse_agent] decide()  ← nó LangGraph
  │       ├── ChatOpenAI(gpt-4o-mini) com contexto + histórico de decisões
  │       ├── LLM chama @tool sales_history("armazem_a", last=30d) via ToolNode
  │       └── LLM retorna: {"action": "request_resupply", "quantity_tons": 50, "from_factory": "F1"}
  │
  ├── guardrails/warehouse.py valida a decisão
  │       └── Rejeita se quantity_tons > capacidade disponível
  │
  ├── Decisão válida → repositories/agent_decision.py persiste
  │
  ├── DecisionEffectProcessor.process() — aplica efeitos colaterais na mesma transação:
  │       ├── order_replenishment → cria PendingOrder (store→warehouse) com deduplicação
  │       ├── confirm_order → reserva estoque + despacha caminhão terceiro (warehouse→store)
  │       ├── request_resupply → cria PendingOrder (warehouse→factory) com deduplicação
  │       ├── send_stock → cria PendingOrder (factory→warehouse) + despacha caminhão
  │       ├── accept_contract → Valhalla route + assign_route (caminhão → in_transit)
  │       ├── request_maintenance → schedule_maintenance (caminhão → maintenance)
  │       └── hold → no-op
  │
  └── Evento publicado no Redis → Dashboard
```

---

## 8. Convenções de Código

- **Idioma:** Todo o código (nomes de variáveis, funções, classes, módulos, commits) deve ser escrito em **inglês** — sem exceções.
- **Nomenclatura expressiva:** Nomes de métodos e variáveis devem ser autoexplicativos, eliminando a necessidade de comentários. Prefira `calculate_replenishment_ticks()` a `calc()` com um comentário explicando o que faz.
- **Sem docstrings:** Não adicionar docstrings nos métodos (blocos de descrição de parâmetros, retorno, exemplos). O código deve se explicar pelos nomes e pela estrutura.
- **Sem comentários redundantes:** Comentários só são aceitáveis para lógica genuinamente não óbvia (ex: fórmulas físicas com contexto de negócio). Nunca use comentários para descrever o que o código faz — renomeie o código.
- **Campos tipados — Python Enum:** Colunas com conjunto fixo de valores válidos usam classes `enum.Enum` definidas em `backend/src/enums/` (package, organizado por domínio: `agents.py`, `trucks.py`, `facilities.py`, `routes.py`, `events.py`, `orders.py`). O `__init__.py` re-exporta tudo — imports sempre via `from src.enums import <Class>`. O tipo da coluna no banco permanece `String` — sem PostgreSQL native ENUM (custo de migration alto em fase de evolução rápida). Guardrails Pydantic enforçam os valores na camada de aplicação. Campos livres/extensíveis (ex: `event_type`, `action`) não usam enum.

---

## 9. Constraints & Considerações

- **Quota OpenAI:** `asyncio.Semaphore(MAX_AGENT_WORKERS)` limita chamadas concorrentes. Monitorar custo por tick (gpt-4o-mini é ~10x mais barato que gpt-4o).
- **Determinismo:** Física nunca usa IA — garante reprodutibilidade e facilita testes.
- **Guardrails first:** Nenhuma decisão de agente afeta o banco sem passar pelo schema Pydantic.
- **TDD obrigatório — fluxo em duas fases:**
  1. **Fase 1 — Testes:** Escreva todos os testes da feature (unitários ou de integração, conforme a natureza da feature). Pare e aguarde aprovação do usuário.
  2. **Fase 2 — Implementação:** Somente após o usuário aprovar os testes, implemente o código da feature.
  - Nunca escreva código de implementação junto com os testes — as fases são separadas e sequenciais.
  - Nunca avance para a próxima feature sem o usuário validar os testes da atual.
- **Testes unitários:** agentes testáveis com `WorldState` mockado e `ChatOpenAI` substituído por `FakeListChatModel` do LangChain; repositories testados com `AsyncSession` mockada.
- **Testes de integração:** features que tocam banco de dados (migrations, seed, repositories em cenários end-to-end) usam banco PostgreSQL efêmero via `testcontainers-python` (`PostgresContainer`) — sem variável de ambiente, sem banco preexistente. Instalar com `pip install -e ".[test]"`.
- **Estrutura de pastas dos testes:** os testes espelham a estrutura de `backend/src/`. Exemplo: testes de `backend/src/world/` ficam em `backend/tests/unit/world/`, não soltos em `backend/tests/unit/`. Sempre criar `__init__.py` nos subdiretórios de teste.
- **Performance:** Evitar N+1 queries — `WorldState` é carregado em uma query com joins.

---

## 10. Próximos Passos

1. ✅ **CLAUDE.md** (você está aqui)
2. **specs/01-specify.md** — Problema, user stories, critérios de aceitação
3. **specs/02-design.md** — Schemas de dados, prompts dos agentes, fluxos de evento
4. **specs/features/** — Tasks por componente (world, agents, mcp, simulation, api, frontend)

---

## 11. Development State — `.specs/state.md`

`.specs/state.md` é o arquivo de controle de progresso do desenvolvimento. O agente deve:

- **Ler `state.md` no início de cada sessão de desenvolvimento** para saber onde parou e o que vem a seguir.
- **Atualizar `state.md` após cada transição de fase** — não apenas ao concluir a feature.
- **Registrar decisões de implementação** na seção "Implementation Decisions" quando algo relevante for decidido durante o desenvolvimento (ex: escolha de biblioteca, trade-off de design não óbvio, desvio do spec).
- **Não usar `state.md` para registrar definições do projeto** — essas vivem em `design.md`, `prd.md` e `CLAUDE.md`.
- O arquivo rastreia exclusivamente o estado de progresso das 18 features em `.specs/features/` — nada mais.

### Ciclo de status por feature

```
pending → tdd_phase1 → in_progress → done
                ↓            ↑
          tdd_rejected ──────┘  (após revisão dos testes)
```

| Transição                     | Quando ocorre                                                            |
| ----------------------------- | ------------------------------------------------------------------------ |
| `pending` → `tdd_phase1`      | Testes escritos, aguardando aprovação do usuário                         |
| `tdd_phase1` → `tdd_rejected` | Usuário rejeitou os testes (`revise ...`) — Notes registra o que revisar |
| `tdd_rejected` → `tdd_phase1` | Testes revisados, aguardando aprovação novamente                         |
| `tdd_phase1` → `in_progress`  | Usuário aprovou os testes (`approved`)                                   |
| `pending` → `in_progress`     | Feature sem TDD — implementação direta                                   |
| `in_progress` → `done`        | Todos os critérios satisfeitos e testes passando                         |

**Ao retomar uma sessão:** se o status for `tdd_phase1`, re-exibir o resumo dos testes escritos e aguardar aprovação. Se for `tdd_rejected`, re-exibir o que precisa revisar (Notes) e corrigir os testes antes de prosseguir.
