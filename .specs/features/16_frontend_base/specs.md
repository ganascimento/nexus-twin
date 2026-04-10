# Feature 16 — Frontend Base

## Objetivo

Implementar a camada de fundação do frontend: tipos TypeScript alinhados com o backend (design.md §1, §3), estado global via Zustand sincronizado por WebSocket, hooks de conexão e seleção, utilitários geo para interpolação de posição de caminhões, e o layout base do `App.tsx`. Ao final desta feature, o frontend tem tipos corretos, estado reativo e conexão em tempo real com o backend — mas nenhuma visualização ainda (features 17 e 18).

---

## Critérios de Aceitacao

### Tipos TypeScript — `types/world.ts`

- [ ] `TruckStatus` usa os valores exatos do enum do backend: `idle`, `evaluating`, `in_transit`, `broken`, `maintenance`
- [ ] `FactoryStatus` usa os valores exatos: `operating`, `stopped`, `reduced_capacity`
- [ ] `WarehouseStatus` usa os valores exatos: `operating`, `rationing`, `offline`
- [ ] `StoreStatus` usa os valores exatos: `open`, `demand_paused`, `offline`
- [ ] `RouteStatus` usa os valores exatos: `active`, `completed`, `interrupted`
- [ ] `OrderStatus` usa os valores exatos: `pending`, `confirmed`, `rejected`, `delivered`, `cancelled`
- [ ] `ChaosEventSource` usa os valores exatos: `user`, `master_agent`, `engine`
- [ ] `ChaosEventStatus` usa os valores exatos: `active`, `resolved`
- [ ] `AgentType` usa os valores exatos: `factory`, `warehouse`, `store`, `truck`, `master`
- [ ] Interface `FactorySnapshot` inclui campos alinhados com design.md §1: `id`, `name`, `lat`, `lng`, `status` (FactoryStatus), e array de `FactoryProductSnapshot` com `material_id`, `stock`, `stock_reserved`, `stock_max`, `production_rate_max`, `production_rate_current`
- [ ] Interface `WarehouseSnapshot` inclui: `id`, `name`, `lat`, `lng`, `region`, `capacity_total`, `status` (WarehouseStatus), e array de `WarehouseStockSnapshot` com `material_id`, `stock`, `stock_reserved`, `min_stock`
- [ ] Interface `StoreSnapshot` inclui: `id`, `name`, `lat`, `lng`, `status` (StoreStatus), e array de `StoreStockSnapshot` com `material_id`, `stock`, `demand_rate`, `reorder_point`
- [ ] Interface `TruckSnapshot` inclui: `id`, `truck_type` (TruckType), `capacity_tons`, `current_lat`, `current_lng`, `base_lat`, `base_lng`, `degradation`, `breakdown_risk`, `status` (TruckStatus), `factory_id` (nullable), `cargo` (JSONB: `{product, quantity, origin, destination}` ou null), `active_route_id` (nullable)
- [ ] Interface `ActiveRoute` inclui: `id`, `truck_id`, `origin_type`, `origin_id`, `dest_type`, `dest_id`, `path` (`[number, number][]`), `timestamps` (`number[]`), `eta_ticks`, `status` (RouteStatus)
- [ ] Interface `WorldStatePayload` espelha design.md §3: `tick`, `simulated_timestamp`, `factories: FactorySnapshot[]`, `warehouses: WarehouseSnapshot[]`, `stores: StoreSnapshot[]`, `trucks: TruckSnapshot[]`, `active_events: ActiveEvent[]`
- [ ] Interface `AgentDecisionPayload` espelha design.md §3: `tick`, `agent_type` (AgentType), `entity_id`, `entity_name`, `action`, `summary`, `reasoning?`
- [ ] Interface `EventPayload` espelha design.md §3: `event_id`, `event_type`, `source` (ChaosEventSource), `entity_type?`, `entity_id?`, `status` (ChaosEventStatus), `tick`, `description`
- [ ] Interface `WSMessage` com `channel: "world_state" | "agent_decisions" | "events"` e `payload` tipado
- [ ] `npx tsc --noEmit` passa com zero erros

### Zustand Store — `store/worldStore.ts`

- [ ] Store exporta tipo `WorldStoreState` com campos: `tick`, `simulatedTimestamp`, `factories` (`FactorySnapshot[]`), `warehouses` (`WarehouseSnapshot[]`), `stores` (`StoreSnapshot[]`), `trucks` (`TruckSnapshot[]`), `activeEvents` (`EventPayload[]`), `recentDecisions` (`AgentDecisionPayload[]`), `isConnected`
- [ ] Action `setWorldState(payload: WorldStatePayload)` substitui o snapshot completo do mundo (tick, timestamp, todas as entidades e eventos)
- [ ] Action `addDecision(payload: AgentDecisionPayload)` adiciona ao array `recentDecisions` (mantém no maximo 100 itens, descartando os mais antigos)
- [ ] Action `updateEvent(payload: EventPayload)` adiciona novo evento ou atualiza existente pelo `event_id`
- [ ] Action `setConnected(connected: boolean)` atualiza flag `isConnected`
- [ ] Store criado com `create` do Zustand, sem middleware (sem persist, sem devtools nesta feature)

### WebSocket Hook — `hooks/useWorldSocket.ts`

- [ ] Hook `useWorldSocket()` conecta ao endpoint `ws://<VITE_API_URL>/ws` ao montar o componente
- [ ] Ao receber mensagem com `channel: "world_state"`, chama `setWorldState` no store
- [ ] Ao receber mensagem com `channel: "agent_decisions"`, chama `addDecision` no store
- [ ] Ao receber mensagem com `channel: "events"`, chama `updateEvent` no store
- [ ] Implementa reconexao automatica com backoff exponencial (1s, 2s, 4s, 8s, max 30s)
- [ ] Atualiza `isConnected` no store ao abrir (`true`) e fechar (`false`) a conexao
- [ ] Envia `{ "type": "ping" }` a cada 30 segundos para manter a conexao (conforme design.md §3)
- [ ] Hook faz cleanup do WebSocket e dos timers (ping, reconnect) ao desmontar

### Hook de Inspecao — `hooks/useInspect.ts`

- [ ] Hook `useInspect()` exporta: `selectedEntityId: string | null`, `selectedEntityType: "factory" | "warehouse" | "store" | "truck" | null`
- [ ] Action `selectEntity(id: string, type: EntityType)` define a entidade selecionada
- [ ] Action `clearSelection()` limpa a selecao (ambos voltam a `null`)
- [ ] Implementado como Zustand store separado (nao faz parte do worldStore)

### Utilitarios Geo — `lib/geo.ts`

- [ ] Funcao `interpolatePosition(path: [number, number][], timestamps: number[], currentTime: number): [number, number]` retorna `[lng, lat]` interpolado linearmente entre dois waypoints com base no tempo
- [ ] Se `currentTime < timestamps[0]`, retorna `path[0]`
- [ ] Se `currentTime > timestamps[last]`, retorna `path[last]`
- [ ] Funcao `calculateBearing(from: [number, number], to: [number, number]): number` retorna angulo em graus (0-360) para rotacao do icone do caminhao

### Layout — `App.tsx`

- [ ] `App.tsx` renderiza `WorldMap` fullscreen (100vw x 100vh) com HUD como overlay
- [ ] `useWorldSocket()` e chamado no `App.tsx` para iniciar conexao WebSocket ao montar
- [ ] Container usa `position: relative` com `WorldMap` absolute fill e HUD overlay com `pointer-events: none` por padrao (habilitado seletivamente nos paineis interativos via feature 18)

---

## Fora do Escopo

- Visualizacao do mapa e layers WebGL — deck.gl, MapLibre, TripsLayer, ScatterplotLayer (feature 17)
- Componentes de HUD: InspectPanel, AgentLog, ChaosPanel, WorldManagement, StatsBar (feature 18)
- Chamadas REST a API para CRUD de entidades (feature 18)
- Testes unitarios do frontend — nao ha logica de negocio complexa; validacao e feita pelo compilador TypeScript e pelas interfaces tipadas
