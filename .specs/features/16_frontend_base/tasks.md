# Tasks — Feature 16: Frontend Base

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — estrutura de pastas (§3 frontend), stack frontend (§2), dependencias (§5), convencoes (§8)
- `.specs/features/16_frontend_base/specs.md` — criterios de aceitacao desta feature
- `.specs/design.md` §1 — schemas de todas as tabelas (campos exatos dos snapshots)
- `.specs/design.md` §3 — rotas WebSocket, interfaces `WSMessage`, `WorldStatePayload`, `AgentDecisionPayload`, `EventPayload`, mensagens do cliente (`ping`, `subscribe`)
- `backend/src/enums/` — valores exatos de cada enum para garantir alinhamento

Nao leia specs de features 17 ou 18. Esta feature nao depende delas.

---

## Plano de Execucao

Os Grupos 1 e 2 rodam em paralelo (sem dependencias entre si).
O Grupo 3 depende dos Grupos 1 e 2 (usa os tipos e o store).
O Grupo 4 e sequencial — roda apos todos os outros para validacao.

---

### Grupo 1 — Tipos TypeScript (um agente)

**Tarefa:** Reescrever `frontend/src/types/world.ts` com todos os tipos alinhados ao backend.

1. Ler `backend/src/enums/` (`agents.py`, `trucks.py`, `facilities.py`, `routes.py`, `events.py`, `orders.py`) para copiar os valores exatos de cada enum.

2. Ler `.specs/design.md` §1 (diagrama de tabelas) para mapear cada coluna para o campo TypeScript correspondente.

3. Ler `.specs/design.md` §3 (rotas WebSocket) para copiar as interfaces de payload exatas.

4. Reescrever `frontend/src/types/world.ts` com:

   **Union types (espelhando enums do backend):**
   - `TruckType = "proprietario" | "terceiro"`
   - `TruckStatus = "idle" | "evaluating" | "in_transit" | "broken" | "maintenance"`
   - `FactoryStatus = "operating" | "stopped" | "reduced_capacity"`
   - `WarehouseStatus = "operating" | "rationing" | "offline"`
   - `StoreStatus = "open" | "demand_paused" | "offline"`
   - `RouteStatus = "active" | "completed" | "interrupted"`
   - `RouteNodeType = "factory" | "warehouse" | "store"`
   - `OrderStatus = "pending" | "confirmed" | "rejected" | "delivered" | "cancelled"`
   - `OrderRequesterType = "store" | "warehouse"`
   - `OrderTargetType = "warehouse" | "factory"`
   - `ChaosEventSource = "user" | "master_agent" | "engine"`
   - `ChaosEventEntityType = "factory" | "warehouse" | "store" | "truck"`
   - `ChaosEventStatus = "active" | "resolved"`
   - `AgentType = "factory" | "warehouse" | "store" | "truck" | "master"`
   - `EntityType = "factory" | "warehouse" | "store" | "truck"`

   **Interfaces de snapshot (espelhando tabelas de design.md §1):**
   - `FactoryProductSnapshot` — `material_id`, `stock`, `stock_reserved`, `stock_max`, `production_rate_max`, `production_rate_current`
   - `FactorySnapshot` — `id`, `name`, `lat`, `lng`, `status: FactoryStatus`, `products: FactoryProductSnapshot[]`
   - `WarehouseStockSnapshot` — `material_id`, `stock`, `stock_reserved`, `min_stock`
   - `WarehouseSnapshot` — `id`, `name`, `lat`, `lng`, `region`, `capacity_total`, `status: WarehouseStatus`, `stocks: WarehouseStockSnapshot[]`
   - `StoreStockSnapshot` — `material_id`, `stock`, `demand_rate`, `reorder_point`
   - `StoreSnapshot` — `id`, `name`, `lat`, `lng`, `status: StoreStatus`, `stocks: StoreStockSnapshot[]`
   - `TruckCargo` — `product: string`, `quantity: number`, `origin: string`, `destination: string`
   - `TruckSnapshot` — `id`, `truck_type: TruckType`, `capacity_tons`, `base_lat`, `base_lng`, `current_lat`, `current_lng`, `degradation`, `breakdown_risk`, `status: TruckStatus`, `factory_id: string | null`, `cargo: TruckCargo | null`, `active_route_id: string | null`
   - `ActiveRoute` — `id`, `truck_id`, `origin_type: RouteNodeType`, `origin_id`, `dest_type: RouteNodeType`, `dest_id`, `path: [number, number][]`, `timestamps: number[]`, `eta_ticks`, `status: RouteStatus`, `started_at`
   - `ActiveEvent` — `event_id`, `event_type`, `source: ChaosEventSource`, `entity_type: ChaosEventEntityType | null`, `entity_id: string | null`, `status: ChaosEventStatus`, `tick`, `description`

   **Interfaces de payload WebSocket (espelhando design.md §3):**
   - `WorldStatePayload` — `tick`, `simulated_timestamp`, `factories: FactorySnapshot[]`, `warehouses: WarehouseSnapshot[]`, `stores: StoreSnapshot[]`, `trucks: TruckSnapshot[]`, `active_events: ActiveEvent[]`
   - `AgentDecisionPayload` — `tick`, `agent_type: AgentType`, `entity_id`, `entity_name`, `action`, `summary`, `reasoning?: string`
   - `EventPayload` — `event_id`, `event_type`, `source: ChaosEventSource`, `entity_type?: ChaosEventEntityType`, `entity_id?: string`, `status: ChaosEventStatus`, `tick`, `description`
   - `WSMessage` — `channel: "world_state" | "agent_decisions" | "events"`, `payload: WorldStatePayload | AgentDecisionPayload | EventPayload`

---

### Grupo 2 — Utilitarios Geo (um agente)

**Tarefa:** Implementar helpers de interpolacao em `frontend/src/lib/geo.ts`.

1. Implementar `interpolatePosition(path: [number, number][], timestamps: number[], currentTime: number): [number, number]`:
   - Se `path` esta vazio, retornar `[0, 0]`
   - Se `currentTime <= timestamps[0]`, retornar `path[0]`
   - Se `currentTime >= timestamps[last]`, retornar `path[last]`
   - Caso contrario, encontrar o segmento `[i, i+1]` onde `timestamps[i] <= currentTime < timestamps[i+1]`
   - Calcular `t = (currentTime - timestamps[i]) / (timestamps[i+1] - timestamps[i])`
   - Retornar `[lng0 + t * (lng1 - lng0), lat0 + t * (lat1 - lat0)]` (interpolacao linear)

2. Implementar `calculateBearing(from: [number, number], to: [number, number]): number`:
   - `from` e `to` sao `[lng, lat]`
   - Converter para radianos
   - Calcular bearing usando formula do great circle: `atan2(sin(dLng) * cos(lat2), cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLng))`
   - Converter resultado para graus (0-360)

---

### Grupo 3 — Store, Hooks e Layout (um agente, depende dos Grupos 1 e 2)

**Tarefa:** Implementar o Zustand store, os hooks de WebSocket e inspecao, e o layout do App.

1. Implementar `frontend/src/store/worldStore.ts`:
   - Importar tipos de `types/world.ts`
   - Definir interface `WorldStoreState` com:
     - Estado: `tick: number`, `simulatedTimestamp: string`, `factories: FactorySnapshot[]`, `warehouses: WarehouseSnapshot[]`, `stores: StoreSnapshot[]`, `trucks: TruckSnapshot[]`, `activeEvents: EventPayload[]`, `recentDecisions: AgentDecisionPayload[]`, `isConnected: boolean`
     - Actions: `setWorldState`, `addDecision`, `updateEvent`, `setConnected`
   - `setWorldState(payload)`: substituir `tick`, `simulatedTimestamp`, e todos os arrays de entidades pelo conteudo do payload
   - `addDecision(payload)`: prepend ao `recentDecisions`; se `length > 100`, truncar os mais antigos com `slice(0, 100)`
   - `updateEvent(payload)`: buscar por `event_id` no array `activeEvents` — se encontrar, atualizar; se nao, adicionar. Remover eventos com `status === "resolved"` do array
   - `setConnected(connected)`: atualizar flag
   - Exportar `useWorldStore = create<WorldStoreState>(...)`

2. Implementar `frontend/src/hooks/useWorldSocket.ts`:
   - Usar `useEffect` com cleanup para gerenciar ciclo de vida do WebSocket
   - Construir URL: `const wsUrl = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/^http/, "ws") + "/ws"`
   - `onopen`: chamar `useWorldStore.getState().setConnected(true)`; iniciar interval de ping (30s)
   - `onmessage`: parsear JSON como `WSMessage`, despachar para action correta do store baseado em `message.channel`
   - `onclose`: chamar `setConnected(false)`; limpar interval de ping; agendar reconexao com backoff (delay inicial 1s, dobra a cada tentativa, max 30s; resetar delay ao conectar com sucesso)
   - `onerror`: logar erro no console
   - Cleanup no `useEffect`: fechar WebSocket, limpar timers de ping e reconnect
   - Hook nao retorna nada (side-effect puro)

3. Implementar `frontend/src/hooks/useInspect.ts`:
   - Criar Zustand store separado com `create`
   - Estado: `selectedEntityId: string | null`, `selectedEntityType: EntityType | null`
   - Action `selectEntity(id: string, type: EntityType)`: setar ambos os campos
   - Action `clearSelection()`: setar ambos para `null`
   - Exportar `useInspect = create<InspectState>(...)`

4. Atualizar `frontend/src/App.tsx`:
   - Importar `WorldMap` de `./map/WorldMap`
   - Importar `useWorldSocket` de `./hooks/useWorldSocket`
   - Chamar `useWorldSocket()` no corpo do componente
   - Renderizar:
     ```tsx
     <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden" }}>
       <WorldMap />
       {/* HUD overlay — feature 18 */}
     </div>
     ```
   - O `WorldMap` atual retorna `null` (stub) — isso e esperado nesta feature

---

### Grupo 4 — Validacao (sequencial, apos todos os grupos)

**Tarefa:** Verificar que o frontend compila e os tipos estao consistentes.

1. Rodar `npx tsc --noEmit` em `frontend/` e confirmar zero erros
2. Verificar que `worldStore.ts` exporta `useWorldStore` com todos os campos e actions definidos em specs.md
3. Verificar que `useWorldSocket.ts` importa corretamente de `worldStore` e `types/world`
4. Verificar que `useInspect.ts` exporta `useInspect` como Zustand store separado
5. Verificar que `App.tsx` chama `useWorldSocket()` e renderiza `WorldMap` dentro do container fullscreen
6. Verificar que `geo.ts` exporta `interpolatePosition` e `calculateBearing`

Se alguma verificacao falhar, corrigir e rodar novamente.

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos. `npx tsc --noEmit` passa com zero erros.
TDD nao se aplica — nao ha logica de negocio testavel; a validacao e feita pelo compilador TypeScript.
Atualizar `state.md`: setar o status da feature `16` para `done`.
