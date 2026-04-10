# Feature 17 — Frontend Map

## Objetivo

Implementar a visualizacao game-like do mapa: o canvas WebGL fullscreen com MapLibre GL JS como mapa base (tiles do Martin) e deck.gl sobreposto para renderizar as entidades do mundo — fabricas, armazens e lojas como nos vivos (raio proporcional ao estoque), caminhoes animados ao longo das rotas reais, rotas coloridas por status, e icones de eventos de caos. Ao final, o usuario ve o mapa de Sao Paulo com todas as entidades do mundo se atualizando em tempo real a cada tick via WebSocket.

---

## Criterios de Aceitacao

### Configuracao do Mapa — `map/mapConfig.ts`

- [ ] Viewport inicial centrado no estado de Sao Paulo: `latitude: -22.9`, `longitude: -47.1`, `zoom: 7`
- [ ] URL do tile server configuravel via `VITE_TILE_SERVER_URL` (default: `http://localhost:3001`)
- [ ] Estilo do mapa base definido como mapa escuro/neutro para contraste com as layers coloridas de deck.gl (ex: estilo dark-matter ou similar do MapLibre)
- [ ] Exporta constantes reutilizaveis: `INITIAL_VIEW_STATE`, `MAP_STYLE`

### Canvas Principal — `map/WorldMap.tsx`

- [ ] Renderiza MapLibre GL JS como mapa base (usando a URL de tiles do Martin via `mapConfig.ts`)
- [ ] deck.gl `DeckGL` sobreposto ao MapLibre como overlay (controller habilitado para pan/zoom/tilt)
- [ ] Layers carregadas a partir do Zustand store (`useWorldStore`): `NodesLayer`, `TrucksLayer`, `RoutesLayer`, `EventsLayer`
- [ ] Layers re-renderizam automaticamente quando o store muda (novo tick via WebSocket)
- [ ] `onClick` no deck.gl identifica o objeto clicado (fabrica, armazem, loja ou caminhao) e chama `useInspect().selectEntity(id, type)`
- [ ] Clique em area vazia do mapa chama `useInspect().clearSelection()`
- [ ] Componente ocupa 100% do container pai (width/height: 100%)

### Nos Vivos — `map/layers/NodesLayer.ts`

- [ ] Usa `ScatterplotLayer` do deck.gl para renderizar fabricas, armazens e lojas como circulos no mapa
- [ ] Recebe arrays `factories`, `warehouses`, `stores` do store como input
- [ ] Posicao de cada no: `[entity.lng, entity.lat]`
- [ ] **Raio proporcional ao estoque:** raio do circulo escala com o nivel de estoque total da entidade (soma de todos os produtos). Raio minimo visivel mesmo com estoque zero
- [ ] **Cor por tipo de entidade:** cores distintas para fabricas (ex: azul), armazens (ex: amarelo), lojas (ex: verde) — distinguiveis a distancia
- [ ] **Cor de alerta:** entidades em estado critico (estoque total abaixo do minimo total, ou `status !== "operating"/"open"`) mudam para vermelho
- [ ] Propriedade `pickable: true` para que o clique funcione
- [ ] Cada objeto retornado pelo picking inclui `id` e `entityType` para o handler de `onClick` do WorldMap

### Caminhoes Animados — `map/layers/TrucksLayer.ts`

- [ ] Usa `TripsLayer` do `@deck.gl/geo-layers` para animar caminhoes ao longo das rotas
- [ ] Recebe array `trucks` do store e as rotas ativas correspondentes
- [ ] Cada trip: `path: [[lng, lat], ...]` e `timestamps: [ms, ...]` extraidos da rota ativa do caminhao
- [ ] `currentTime` calculado a partir do tick atual e do `simulated_timestamp` do WorldState — usado para interpolar a posicao
- [ ] Caminhoes sem rota ativa (`active_route_id === null`) renderizados como pontos estaticos em `[current_lng, current_lat]` (usar `ScatterplotLayer` ou `IconLayer` separado)
- [ ] **Cor por tipo:** caminhoes proprietarios em uma cor (ex: ciano), terceiros em outra (ex: laranja)
- [ ] **Indicador de degradacao:** cor do trail/ponto muda gradualmente de verde para amarelo para vermelho conforme `degradation` aumenta (0-1)
- [ ] Propriedade `pickable: true` para clique
- [ ] Trail width e trail length configurados para visibilidade em zoom 7-12

### Rotas com Status — `map/layers/RoutesLayer.ts`

- [ ] Usa `PathLayer` do deck.gl para renderizar segmentos de rotas
- [ ] Recebe rotas ativas do store (extraidas dos trucks com `active_route_id`)
- [ ] Cada rota: `path: [[lng, lat], ...]` completo do campo `path` da rota
- [ ] **Cor por status da rota:** verde (`active` sem evento), amarelo (rota com evento de caos proximo), vermelho (rota com `route_blocked` ativo)
- [ ] Width da rota: 3-5px, com opacity reduzida para nao sobrepor os nos
- [ ] Rotas completadas (`completed`) e interrompidas (`interrupted`) nao sao renderizadas

### Eventos de Caos — `map/layers/EventsLayer.ts`

- [ ] Usa `IconLayer` do deck.gl para renderizar icones de eventos de caos ativos
- [ ] Recebe `activeEvents` do store
- [ ] Posicao: usa `lat`/`lng` da entidade afetada (buscar no store pelo `entity_id`). Eventos sem entidade (ex: greve geral) renderizados em posicao fixa (centro do mapa ou nao renderizados)
- [ ] **Icone por tipo de evento:** icones distintos ou cores distintas para cada `event_type` (nao precisa de sprites complexos — circulos com borda e cor diferente sao suficientes)
- [ ] Propriedade `pickable: true` para que o clique mostre detalhes do evento
- [ ] Apenas eventos com `status: "active"` sao renderizados

### Geral

- [ ] `npx tsc --noEmit` passa com zero erros
- [ ] Mapa renderiza sem crash quando o store esta vazio (estado inicial antes do primeiro tick)
- [ ] Mapa renderiza corretamente com dados de teste (ao menos fabricas e armazens visiveis como nos)

---

## Fora do Escopo

- Componentes de HUD sobrepostos ao mapa: InspectPanel, AgentLog, ChaosPanel, WorldManagement, StatsBar (feature 18)
- Interacao de criacao/edicao de entidades pelo mapa (feature 18)
- Sprites ou assets graficos elaborados — icones simples e circulos coloridos sao suficientes
- Animacao de particulas ou efeitos visuais alem do trail do TripsLayer
- Responsividade mobile — o dashboard e desktop-first
