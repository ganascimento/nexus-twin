# Tasks — Feature 17: Frontend Map

## Antes de Comecar

Leia estes arquivos por completo antes de escrever qualquer codigo:

- `CLAUDE.md` — stack frontend (§2, §4.7), estrutura de pastas frontend (§3), dependencias (§5)
- `.specs/features/17_frontend_map/specs.md` — criterios de aceitacao desta feature
- `.specs/design.md` §1 — schemas das tabelas (campos de cada entidade: coordenadas, status, estoque)
- `.specs/design.md` §3 — interfaces WebSocket (WorldStatePayload, snapshots de entidades)
- `frontend/src/types/world.ts` — tipos implementados na feature 16 (necessarios para tipar as layers)
- `frontend/src/store/worldStore.ts` — store Zustand implementado na feature 16 (fonte de dados das layers)
- `frontend/src/hooks/useInspect.ts` — hook de selecao implementado na feature 16 (usado pelo onClick do mapa)
- `frontend/src/lib/geo.ts` — helpers de interpolacao implementados na feature 16 (usados pelo TrucksLayer)

Nao leia specs de feature 18. Esta feature nao depende dela.

---

## Plano de Execucao

O Grupo 1 roda primeiro (configuracao base do mapa).
Os Grupos 2, 3, 4 e 5 rodam em paralelo (cada layer e independente).
O Grupo 6 depende de todos os anteriores (integra as layers no WorldMap).
O Grupo 7 e sequencial — validacao apos tudo.

---

### Grupo 1 — Configuracao do Mapa (um agente)

**Tarefa:** Implementar `frontend/src/map/mapConfig.ts` com as constantes de configuracao do mapa.

1. Definir e exportar `INITIAL_VIEW_STATE`:
   - `latitude: -22.9` (centro do estado de SP)
   - `longitude: -47.1`
   - `zoom: 7` (abrange o estado inteiro)
   - `pitch: 0`
   - `bearing: 0`
   - `minZoom: 5`
   - `maxZoom: 16`

2. Definir e exportar `MAP_STYLE`:
   - URL para o estilo do mapa base servido pelo Martin
   - Usar `VITE_TILE_SERVER_URL` do environment: `${import.meta.env.VITE_TILE_SERVER_URL || "http://localhost:3001"}`
   - Definir um estilo MapLibre dark/neutro como JSON inline ou URL para estilo compativel com Martin/PMTiles
   - O estilo deve ser minimalista (fundo escuro, rodovias sutis) para dar destaque as layers de deck.gl

3. Exportar constantes de cores das entidades para reuso nas layers:
   - `FACTORY_COLOR: [66, 133, 244]` (azul)
   - `WAREHOUSE_COLOR: [251, 188, 4]` (amarelo)
   - `STORE_COLOR: [52, 168, 83]` (verde)
   - `TRUCK_PROPRIETARIO_COLOR: [0, 188, 212]` (ciano)
   - `TRUCK_TERCEIRO_COLOR: [255, 152, 0]` (laranja)
   - `ALERT_COLOR: [234, 67, 53]` (vermelho)
   - `ROUTE_ACTIVE_COLOR: [76, 175, 80]` (verde)
   - `ROUTE_WARNING_COLOR: [255, 235, 59]` (amarelo)
   - `ROUTE_BLOCKED_COLOR: [244, 67, 54]` (vermelho)

---

### Grupo 2 — NodesLayer (um agente)

**Tarefa:** Implementar `frontend/src/map/layers/NodesLayer.ts`.

1. Exportar funcao `createNodesLayer(factories, warehouses, stores)` que retorna um `ScatterplotLayer` (ou array de layers).

2. Preparar dados de entrada:
   - Mapear cada fabrica para `{ id, entityType: "factory", position: [lng, lat], totalStock, isAlert, color }`
   - `totalStock` = soma de `product.stock` de todos os `products` da fabrica
   - `isAlert` = `status !== "operating"` ou totalStock abaixo de um threshold
   - Repetir para armazens (soma de `stocks[].stock`, alert se `status !== "operating"`) e lojas (soma de `stocks[].stock`, alert se `status !== "open"`)

3. Configurar `ScatterplotLayer`:
   - `id: "nodes-layer"`
   - `data`: array combinado de todas as entidades mapeadas
   - `getPosition: d => d.position`
   - `getRadius: d => Math.max(500, Math.sqrt(d.totalStock) * 200)` — raio minimo de 500m para visibilidade, escala com raiz quadrada do estoque para evitar circulos gigantes
   - `getFillColor: d => d.isAlert ? ALERT_COLOR : d.color` — vermelho se em alerta, senao cor do tipo
   - `radiusUnits: "meters"`
   - `pickable: true`
   - `autoHighlight: true`
   - `highlightColor: [255, 255, 255, 80]`
   - `onClick` nao e configurado aqui — e tratado pelo `onLayerClick` do DeckGL no WorldMap

4. Cada objeto no data deve incluir `id` e `entityType` para que o picking handler do WorldMap consiga chamar `useInspect().selectEntity(id, type)`.

---

### Grupo 3 — TrucksLayer (um agente)

**Tarefa:** Implementar `frontend/src/map/layers/TrucksLayer.ts`.

1. Ler `frontend/src/lib/geo.ts` para entender as funcoes `interpolatePosition` e `calculateBearing` disponiveis.

2. Exportar funcao `createTrucksLayers(trucks, routes, currentTime)` que retorna um array de layers:
   - Um `TripsLayer` para caminhoes com rota ativa (animados)
   - Um `ScatterplotLayer` para caminhoes sem rota (estaticos — idle, broken, maintenance)

3. Para o `TripsLayer` (caminhoes em transito):
   - Filtrar caminhoes com `active_route_id !== null`
   - Para cada caminhao, encontrar a rota correspondente no array `routes`
   - `data`: array de objetos `{ id, entityType: "truck", path: route.path, timestamps: route.timestamps, truckType, degradation }`
   - `id: "trucks-trips-layer"`
   - `getPath: d => d.path`
   - `getTimestamps: d => d.timestamps`
   - `getColor: d => getDegradationColor(d.degradation)` — gradiente verde (0) -> amarelo (0.5) -> vermelho (1.0)
   - `currentTime`: passado como parametro (timestamp em ms correspondente ao tick atual)
   - `trailLength: 600000` (10 minutos em ms — trail visivel)
   - `widthMinPixels: 4`
   - `pickable: true`
   - `jointRounded: true`
   - `capRounded: true`

4. Para o `ScatterplotLayer` (caminhoes parados):
   - Filtrar caminhoes com `active_route_id === null`
   - `data`: array de objetos `{ id, entityType: "truck", position: [current_lng, current_lat], truckType, degradation, status }`
   - `id: "trucks-static-layer"`
   - `getPosition: d => d.position`
   - `getRadius: 400` (raio fixo, menor que nos de entidades)
   - `getFillColor: d => d.truckType === "proprietario" ? TRUCK_PROPRIETARIO_COLOR : TRUCK_TERCEIRO_COLOR`
   - `getLineColor: d => getDegradationColor(d.degradation)` — borda indica degradacao
   - `lineWidthMinPixels: 2`
   - `stroked: true`
   - `pickable: true`

5. Implementar helper interno `getDegradationColor(degradation: number): [number, number, number]`:
   - `degradation < 0.3` -> verde `[76, 175, 80]`
   - `0.3 <= degradation < 0.6` -> amarelo `[255, 235, 59]`
   - `0.6 <= degradation < 0.8` -> laranja `[255, 152, 0]`
   - `degradation >= 0.8` -> vermelho `[244, 67, 54]`

---

### Grupo 4 — RoutesLayer (um agente)

**Tarefa:** Implementar `frontend/src/map/layers/RoutesLayer.ts`.

1. Exportar funcao `createRoutesLayer(routes, activeEvents)` que retorna um `PathLayer`.

2. Filtrar apenas rotas com `status === "active"`.

3. Para cada rota, determinar a cor:
   - Verificar se algum evento ativo (`activeEvents`) com `event_type === "route_blocked"` afeta a rota (por `entity_id` do caminhao ou por overlap geografico — simplificar: se o caminhao dono da rota tem um evento `route_blocked` ativo, a rota e vermelha)
   - Sem evento: `ROUTE_ACTIVE_COLOR` (verde)
   - Com evento proximo/alerta: `ROUTE_WARNING_COLOR` (amarelo)
   - Com bloqueio: `ROUTE_BLOCKED_COLOR` (vermelho)

4. Configurar `PathLayer`:
   - `id: "routes-layer"`
   - `data`: array de rotas ativas com cor calculada
   - `getPath: d => d.path`
   - `getColor: d => d.color`
   - `getWidth: 3`
   - `widthUnits: "pixels"`
   - `opacity: 0.6` (nao sobrepor os nos)
   - `pickable: false` (rotas nao sao clicaveis)
   - `jointRounded: true`
   - `capRounded: true`

---

### Grupo 5 — EventsLayer (um agente)

**Tarefa:** Implementar `frontend/src/map/layers/EventsLayer.ts`.

1. Exportar funcao `createEventsLayer(activeEvents, entityPositions)` que retorna um `ScatterplotLayer` (simplificacao — sem sprites, usar circulos estilizados).

2. `entityPositions` e um `Map<string, [number, number]>` pre-construido no WorldMap: mapeia `entity_id` -> `[lng, lat]` para todas as entidades (factories, warehouses, stores, trucks).

3. Para cada evento ativo (`status === "active"`):
   - Se `entity_id` existe e esta no `entityPositions`, usar a posicao da entidade
   - Se `entity_id` nao existe ou e null, nao renderizar o evento no mapa (eventos globais como greve nao tem posicao)

4. Configurar `ScatterplotLayer`:
   - `id: "events-layer"`
   - `data`: array de eventos com posicao resolvida
   - `getPosition: d => d.position`
   - `getRadius: 800` (maior que nos normais para chamar atencao)
   - `getFillColor: [234, 67, 53, 160]` (vermelho semi-transparente)
   - `getLineColor: [255, 255, 255]` (borda branca)
   - `stroked: true`
   - `lineWidthMinPixels: 3`
   - `radiusUnits: "meters"`
   - `pickable: true`
   - Cada objeto inclui `eventId`, `eventType` e `description` para o picking handler

---

### Grupo 6 — WorldMap (sequencial, depende dos Grupos 1-5)

**Tarefa:** Integrar todas as layers no `frontend/src/map/WorldMap.tsx`.

1. Importar `Map` de `react-map-gl/maplibre` (ou `maplibre-gl` diretamente com wrapper React)
   - Verificar se `react-map-gl` esta no `package.json`; se nao, adicionar como dependencia (`npm install react-map-gl`)
   - Alternativa: usar `DeckGL` standalone com `MapView` — avaliar o que compila sem dependencias extras

2. Importar `DeckGL` de `deck.gl`

3. Importar as funcoes de criacao de layers:
   - `createNodesLayer` de `./layers/NodesLayer`
   - `createTrucksLayers` de `./layers/TrucksLayer`
   - `createRoutesLayer` de `./layers/RoutesLayer`
   - `createEventsLayer` de `./layers/EventsLayer`

4. Importar `INITIAL_VIEW_STATE`, `MAP_STYLE` de `./mapConfig`

5. Importar `useWorldStore` e `useInspect`

6. No componente `WorldMap`:
   - Ler estado do store: `const { factories, warehouses, stores, trucks, activeEvents, tick, simulatedTimestamp } = useWorldStore()`
   - Ler actions do inspect: `const { selectEntity, clearSelection } = useInspect()`
   - Construir `entityPositions: Map<string, [number, number]>` a partir de todas as entidades (factories/warehouses/stores pelo `lng`/`lat`, trucks pelo `current_lng`/`current_lat`)
   - Calcular `currentTime` para o TripsLayer a partir de `simulatedTimestamp` (converter ISO 8601 para ms)
   - Extrair rotas ativas dos trucks (se o WorldStatePayload incluir rotas; caso contrario, usar array vazio inicialmente)
   - Montar array de layers: `[createNodesLayer(...), ...createTrucksLayers(...), createRoutesLayer(...), createEventsLayer(...)]`

7. Handler `onClick`:
   - Se `info.object` existe e tem `entityType` e `id`: chamar `selectEntity(info.object.id, info.object.entityType)`
   - Se `info.object` nao existe (clique no vazio): chamar `clearSelection()`

8. Renderizar:
   ```tsx
   <DeckGL
     initialViewState={INITIAL_VIEW_STATE}
     controller={true}
     layers={layers}
     onClick={handleClick}
     style={{ width: "100%", height: "100%" }}
   >
     <Map mapStyle={MAP_STYLE} />
   </DeckGL>
   ```

9. Garantir que o componente nao crasha quando o store esta vazio (arrays vazios — estado inicial antes do primeiro tick). Todas as funcoes de layer devem lidar com arrays vazios graciosamente.

---

### Grupo 7 — Validacao (sequencial, apos todos os grupos)

**Tarefa:** Verificar que o mapa compila e renderiza.

1. Rodar `npx tsc --noEmit` em `frontend/` e confirmar zero erros
2. Verificar que `package.json` tem todas as dependencias necessarias (deck.gl, maplibre-gl, react-map-gl se usado)
3. Verificar que `WorldMap.tsx` importa e usa todas as 4 layers
4. Verificar que `mapConfig.ts` exporta `INITIAL_VIEW_STATE` e `MAP_STYLE`
5. Verificar que cada layer retorna o tipo correto do deck.gl (`ScatterplotLayer`, `TripsLayer`, `PathLayer`)
6. Verificar que todos os objetos retornados pelo picking incluem `id` e `entityType` (ou `eventId` para eventos)

Se alguma verificacao falhar, corrigir e rodar novamente.

---

## Condicao de Conclusao

Todos os criterios de aceitacao em `specs.md` estao satisfeitos. `npx tsc --noEmit` passa com zero erros. Mapa renderiza sem crash com store vazio.
TDD nao se aplica — layers de deck.gl sao declarativas/visuais, sem logica de negocio testavel por unit tests.
Atualizar `state.md`: setar o status da feature `17` para `done`.
