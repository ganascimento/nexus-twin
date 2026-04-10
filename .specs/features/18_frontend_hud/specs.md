# Feature 18 — Frontend HUD

## Objetivo

Implementar os componentes de HUD (Heads-Up Display) sobrepostos ao mapa: barra de status com controles da simulação, painel de inspeção de entidades, feed de decisões dos agentes, painel de caos e gestão do mundo (CRUD de entidades e materiais). Ao final, o usuário tem controle completo sobre a simulação — observa, inspeciona, injeta caos e molda o mundo — tudo via dashboard, sem tocar no backend diretamente. Esta feature completa o frontend e entrega a experiência de "game master" descrita no PRD §9.

---

## Critérios de Aceitação

### Infraestrutura — API Client

- [ ] Módulo `lib/api.ts` exporta funções tipadas para todas as chamadas REST usadas pelo HUD, com base URL lida de `VITE_API_URL` (design.md §2)
- [ ] Todas as chamadas usam `fetch` nativo com tratamento de erro consistente (status !== 2xx lança erro com mensagem do backend)
- [ ] Tipos de request/response alinhados com os schemas de `api/models/` do backend (design.md §2)

### StatsBar — `hud/StatsBar.tsx`

- [ ] Renderiza como barra fixa no topo do viewport, sobreposta ao mapa com `pointer-events: auto`
- [ ] Exibe tick atual e timestamp simulado (lidos do `worldStore`)
- [ ] Exibe indicador de conexão WebSocket (verde = conectado, vermelho = desconectado, usando `isConnected` do store)
- [ ] Exibe contagem de eventos de caos ativos (`activeEvents.length` do store)
- [ ] Exibe contadores de saúde do ecossistema derivados do store: número de entidades em estado crítico (fábricas `stopped`/`reduced_capacity`, armazéns `rationing`/`offline`, lojas `demand_paused`/`offline`, caminhões `broken`)
- [ ] Botão Start/Stop simulação — chama `POST /api/v1/simulation/start` ou `POST /api/v1/simulation/stop` conforme estado atual
- [ ] Exibe estado da simulação (`running`/`stopped`) obtido de `GET /api/v1/simulation/status` ao montar e atualizado após cada ação
- [ ] Controle de velocidade dos ticks — input numérico com mínimo 10 segundos, chama `PATCH /api/v1/simulation/speed` (design.md §2)
- [ ] Botão de avanço manual de tick — chama `POST /api/v1/simulation/tick`, habilitado apenas quando simulação está parada

### InspectPanel — `hud/InspectPanel.tsx`

- [ ] Renderiza como painel lateral direito, sobreposto ao mapa, com `pointer-events: auto`
- [ ] Visível apenas quando `useInspect().selectedEntityId` não é null; escondido caso contrário
- [ ] Botão de fechar que chama `clearSelection()`
- [ ] **Fábrica selecionada:** exibe nome, status, e para cada produto: `material_id`, `stock`, `stock_reserved`, `stock_max`, `production_rate_current`, `production_rate_max` — dados de `FactorySnapshot` no store
- [ ] **Armazém selecionado:** exibe nome, região, `capacity_total`, status, e para cada produto: `material_id`, `stock`, `stock_reserved`, `min_stock` — dados de `WarehouseSnapshot` no store
- [ ] **Loja selecionada:** exibe nome, status, e para cada produto: `material_id`, `stock`, `demand_rate`, `reorder_point` — dados de `StoreSnapshot` no store
- [ ] **Caminhão selecionado:** exibe `truck_type`, `capacity_tons`, `degradation` (com barra visual verde→amarelo→vermelho), `breakdown_risk`, `status`, `cargo` (se houver), `factory_id` (se proprietário) — dados de `TruckSnapshot` no store
- [ ] Exibe histórico de decisões recentes da entidade selecionada, filtrado de `recentDecisions` do store por `entity_id`

### AgentLog — `hud/AgentLog.tsx`

- [ ] Renderiza como painel inferior ou lateral, sobreposto ao mapa, com `pointer-events: auto` e scroll vertical
- [ ] Exibe lista de decisões recentes de `recentDecisions` do store, ordenadas por tick decrescente (mais recente no topo)
- [ ] Cada entrada mostra: tick, `agent_type` (com badge colorido por tipo), `entity_name`, `action`, `summary`
- [ ] Clique em uma entrada chama `useInspect().selectEntity(entity_id, agent_type)` para navegar ao agente no mapa (exceto `agent_type === "master"`)
- [ ] Limite visual de ~50 itens visíveis com scroll; os 100 itens do store são mantidos em memória

### ChaosPanel — `hud/ChaosPanel.tsx`

- [ ] Renderiza como painel flutuante ou seção expandível, com `pointer-events: auto`
- [ ] Seção de injeção: botões/formulário para criar evento de caos via `POST /api/v1/chaos/events` (design.md §2)
- [ ] Tipos de evento disponíveis para injeção manual (PRD §7): `route_blocked`, `machine_breakdown`, `demand_spike`, `regional_storm`, `trucker_strike`, `truck_breakdown`, `demand_zero`
- [ ] Formulário permite selecionar `event_type` e preencher `payload` adequado ao tipo (ex: `highway` e `duration_ticks` para `route_blocked`)
- [ ] Seção de eventos ativos: lista eventos de `activeEvents` do store com `event_type`, `source` (badge `[User]` ou `[MasterAgent]`), tick de início
- [ ] Botão "Resolver" em cada evento ativo — chama `POST /api/v1/chaos/events/{id}/resolve`

### WorldManagement — `hud/WorldManagement.tsx`

- [ ] Renderiza como painel/dialog acessível por botão no HUD, com `pointer-events: auto`
- [ ] **Gestão de Materiais:** listar materiais via `GET /api/v1/materials`, criar via `POST /api/v1/materials`, editar nome via `PATCH /api/v1/materials/{id}`, desativar via `PATCH /api/v1/materials/{id}/deactivate`
- [ ] **CRUD de Fábricas:** listar via store, criar via `POST /api/v1/entities/factories`, deletar via `DELETE /api/v1/entities/factories/{id}`
- [ ] **CRUD de Armazéns:** listar via store, criar via `POST /api/v1/entities/warehouses`, deletar via `DELETE /api/v1/entities/warehouses/{id}`
- [ ] **CRUD de Lojas:** listar via store, criar via `POST /api/v1/entities/stores`, deletar via `DELETE /api/v1/entities/stores/{id}`
- [ ] **CRUD de Caminhões:** listar via store, criar via `POST /api/v1/entities/trucks`, deletar via `DELETE /api/v1/entities/trucks/{id}`
- [ ] **Ajuste de estoque:** formulário para ajustar estoque de qualquer entidade via `PATCH /api/v1/entities/{type}/{id}/stock` (design.md §2)
- [ ] Formulários de criação de fábrica/armazém/loja incluem seleção de materiais como combo multi-seleção a partir de materiais ativos carregados da API (PRD §6)
- [ ] Campos de configuração por material (stock_max, production_rate_max, min_stock, demand_rate, reorder_point) expandidos dinamicamente após selecionar os materiais

### Layout & Integração — `App.tsx`

- [ ] `App.tsx` renderiza todos os componentes HUD como overlay sobre o `WorldMap`
- [ ] HUD container usa `pointer-events: none` com cada painel individual definindo `pointer-events: auto` nos seus elementos interativos
- [ ] Componentes de HUD coexistem sem obstruir a interação com o mapa (pan/zoom/clique passam para deck.gl quando não interceptados por um painel)
- [ ] `npx tsc --noEmit` passa com zero erros
- [ ] Todos os componentes renderizam sem crash quando o store está vazio (estado inicial antes do primeiro tick)

---

## Fora do Escopo

- Alterações no backend — todos os endpoints REST e WebSocket já existem (features 13, 14)
- Alterações nas layers do mapa — NodesLayer, TrucksLayer, RoutesLayer, EventsLayer (feature 17)
- Edição inline de entidades existentes (PATCH) — esta feature cobre apenas criação e deleção; edição completa pode ser adicionada como melhoria futura
- Responsividade mobile — dashboard é desktop-first
- Sprites, assets gráficos ou animações no HUD — shadcn/ui e Tailwind são suficientes
- Testes unitários do frontend — não há lógica de negócio complexa; validação é feita pelo compilador TypeScript e pelas interfaces tipadas (precedente da feature 16)
