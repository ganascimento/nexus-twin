# Tasks — Feature 18: Frontend HUD

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:
- `CLAUDE.md` — estrutura de pastas (§3 frontend), stack frontend (§2), convenções (§8)
- `.specs/features/18_frontend_hud/specs.md` — critérios de aceitação
- `.specs/design.md` §2 (endpoints HTTP) e §3 (WebSocket messages) — contratos da API
- `frontend/src/types/world.ts` — tipos TypeScript existentes
- `frontend/src/store/worldStore.ts` — estado global Zustand
- `frontend/src/hooks/useInspect.ts` — hook de seleção de entidade
- `frontend/src/App.tsx` — layout atual (contém placeholder para HUD)
- `frontend/src/map/WorldMap.tsx` — canvas do mapa (para entender a integração)

Não leia specs de features do backend. O frontend consome endpoints prontos.

---

## Plano de Execução

O Grupo 1 roda primeiro (instala dependências e cria o API client compartilhado).
Os Grupos 2–6 rodam em paralelo após o Grupo 1 (componentes independentes).
O Grupo 7 é sequencial — integra tudo no `App.tsx` e valida.

Não há fase de TDD — esta feature é UI pura. Validação via `npx tsc --noEmit` e renderização sem crash.

---

### Grupo 1 — Infraestrutura: shadcn/ui + API Client (um agente)

**Tarefa:** Instalar componentes shadcn/ui necessários e criar o módulo de API client.

1. Instalar componentes shadcn/ui via CLI (`npx shadcn@latest add`):
   - `button`, `input`, `select`, `dialog`, `scroll-area`, `badge`, `card`, `separator`, `label`, `textarea`
   - Confirmar que os componentes são criados em `frontend/src/components/ui/`

2. Criar `frontend/src/lib/api.ts`:
   - Constante `BASE_URL` lida de `import.meta.env.VITE_API_URL` (default `http://localhost:8000`)
   - Helper genérico `apiFetch<T>(path: string, options?: RequestInit): Promise<T>` que:
     - Prefixa o path com `${BASE_URL}/api/v1`
     - Adiciona `Content-Type: application/json` em requests com body
     - Lança erro com mensagem do backend se `response.ok === false`
   - Funções de simulação:
     - `getSimulationStatus(): Promise<SimulationStatus>` — `GET /simulation/status`
     - `startSimulation(): Promise<void>` — `POST /simulation/start`
     - `stopSimulation(): Promise<void>` — `POST /simulation/stop`
     - `advanceTick(): Promise<void>` — `POST /simulation/tick`
     - `setSimulationSpeed(seconds: number): Promise<void>` — `PATCH /simulation/speed`
   - Funções de caos:
     - `injectChaosEvent(data: ChaosEventCreate): Promise<ChaosEventResponse>` — `POST /chaos/events`
     - `resolveChaosEvent(eventId: string): Promise<void>` — `POST /chaos/events/{id}/resolve`
   - Funções de materiais:
     - `listMaterials(activeOnly?: boolean): Promise<MaterialResponse[]>` — `GET /materials`
     - `createMaterial(data: MaterialCreate): Promise<MaterialResponse>` — `POST /materials`
     - `updateMaterial(id: string, data: MaterialUpdate): Promise<MaterialResponse>` — `PATCH /materials/{id}`
     - `deactivateMaterial(id: string): Promise<MaterialResponse>` — `PATCH /materials/{id}/deactivate`
   - Funções de entidades:
     - `createFactory(data: FactoryCreate): Promise<FactoryResponse>` — `POST /entities/factories`
     - `deleteFactory(id: string): Promise<void>` — `DELETE /entities/factories/{id}`
     - `createWarehouse(data: WarehouseCreate): Promise<WarehouseResponse>` — `POST /entities/warehouses`
     - `deleteWarehouse(id: string): Promise<void>` — `DELETE /entities/warehouses/{id}`
     - `createStore(data: StoreCreate): Promise<StoreResponse>` — `POST /entities/stores`
     - `deleteStore(id: string): Promise<void>` — `DELETE /entities/stores/{id}`
     - `createTruck(data: TruckCreate): Promise<TruckResponse>` — `POST /entities/trucks`
     - `deleteTruck(id: string): Promise<void>` — `DELETE /entities/trucks/{id}`
     - `adjustStock(entityType: string, id: string, materialId: string, delta: number): Promise<void>` — `PATCH /entities/{type}/{id}/stock`
   - Tipos de request/response definidos no mesmo arquivo (ou em `types/api.ts` se ficar grande): `SimulationStatus`, `ChaosEventCreate`, `MaterialCreate`, `MaterialUpdate`, `MaterialResponse`, `FactoryCreate`, `WarehouseCreate`, `StoreCreate`, `TruckCreate`, etc. Alinhados com os schemas de `backend/src/api/models/`

---

### Grupo 2 — StatsBar (um agente)

**Tarefa:** Implementar a barra de status superior com controles da simulação.

Ler antes: `frontend/src/lib/api.ts` (do Grupo 1), `frontend/src/store/worldStore.ts`, `frontend/src/types/world.ts`.

1. Implementar `frontend/src/hud/StatsBar.tsx`:
   - Estado local para `simulationStatus` (running/stopped/unknown) e `tickInterval` (number)
   - Ao montar (`useEffect`): chamar `getSimulationStatus()` para inicializar estado
   - Layout horizontal (flex row) fixo no topo com fundo semi-transparente escuro (Tailwind: `bg-black/80 backdrop-blur`)
   - Seção esquerda — informações do mundo:
     - Tick atual e timestamp simulado (`worldStore.tick`, `worldStore.simulatedTimestamp`)
     - Badge de conexão WebSocket (verde/vermelho baseado em `worldStore.isConnected`)
   - Seção central — indicadores de saúde:
     - Contagem de eventos de caos ativos (de `worldStore.activeEvents.length`)
     - Contagem de entidades em estado crítico: contar fábricas com `status !== "operating"`, armazéns com `status !== "operating"`, lojas com `status !== "open"`, caminhões com `status === "broken"`
   - Seção direita — controles da simulação:
     - Botão Start/Stop (ícone play/pause) — chama `startSimulation()` ou `stopSimulation()`, atualiza estado local
     - Botão Advance Tick (ícone step-forward) — chama `advanceTick()`, desabilitado se `simulationStatus === "running"`
     - Input numérico para velocidade (mínimo 10) com botão "Aplicar" — chama `setSimulationSpeed()`

---

### Grupo 3 — InspectPanel (um agente)

**Tarefa:** Implementar o painel de inspeção lateral para entidades selecionadas.

Ler antes: `frontend/src/hooks/useInspect.ts`, `frontend/src/store/worldStore.ts`, `frontend/src/types/world.ts`.

1. Implementar `frontend/src/hud/InspectPanel.tsx`:
   - Usar `useInspect()` para ler `selectedEntityId` e `selectedEntityType`
   - Se `selectedEntityId === null`: retornar `null` (não renderizar)
   - Renderizar painel lateral direito: `fixed top-0 right-0 h-full w-80` com fundo semi-transparente escuro e scroll vertical
   - Botão de fechar (X) no canto superior direito — chama `clearSelection()`
   - Buscar entidade no store por `selectedEntityId`:
     - `factory`: buscar em `worldStore.factories.find(f => f.id === selectedEntityId)`
     - `warehouse`: buscar em `worldStore.warehouses`
     - `store`: buscar em `worldStore.stores`
     - `truck`: buscar em `worldStore.trucks`
   - **Fábrica:** Card com nome, badge de status (cor por status), tabela de produtos com colunas: Material, Stock, Reserved, Max, Rate Current, Rate Max
   - **Armazém:** Card com nome, região, capacidade total, badge de status, tabela de produtos com: Material, Stock, Reserved, Min Stock
   - **Loja:** Card com nome, badge de status, tabela de produtos com: Material, Stock, Demand/tick, Reorder Point
   - **Caminhão:** Card com ID, badge de tipo (proprietário/terceiro), `capacity_tons`, barra de degradação (0–100%, cor gradiente verde→amarelo→vermelho), `breakdown_risk` em %, badge de status, cargo (se houver: produto, quantidade, origem, destino), `factory_id` se proprietário
   - Seção "Decisões Recentes": filtrar `worldStore.recentDecisions` por `entity_id === selectedEntityId`, exibir últimas 10 com tick, action, summary

---

### Grupo 4 — AgentLog (um agente)

**Tarefa:** Implementar o feed rolante de decisões dos agentes.

Ler antes: `frontend/src/store/worldStore.ts`, `frontend/src/hooks/useInspect.ts`, `frontend/src/types/world.ts`.

1. Implementar `frontend/src/hud/AgentLog.tsx`:
   - Renderizar painel no canto inferior esquerdo: `fixed bottom-0 left-0 w-96 max-h-72` com fundo semi-transparente escuro
   - Título "Agent Decisions" com contagem total
   - Usar `ScrollArea` do shadcn/ui para scroll vertical
   - Ler `recentDecisions` do `worldStore`, já ordenadas por tick decrescente (o store faz o prepend)
   - Cada entrada é um item compacto com:
     - Badge colorido por `agent_type`: factory=azul, warehouse=amarelo, store=verde, truck=ciano, master=roxo
     - `entity_name` em bold
     - `action` como texto secundário
     - `summary` como descrição
     - Tick no canto direito
   - `onClick` em cada entrada: se `agent_type !== "master"`, chamar `useInspect().selectEntity(entry.entity_id, entry.agent_type as EntityType)` — mapear `agent_type` para `EntityType` (excluir "master")
   - Limitar renderização a 50 itens visíveis (slice do array)

---

### Grupo 5 — ChaosPanel (um agente)

**Tarefa:** Implementar o painel de injeção e gerenciamento de eventos de caos.

Ler antes: `frontend/src/lib/api.ts` (do Grupo 1), `frontend/src/store/worldStore.ts`, `frontend/src/types/world.ts`, PRD §7 (tipos de evento de caos).

1. Implementar `frontend/src/hud/ChaosPanel.tsx`:
   - Renderizar como painel expandível/colapsável no canto inferior direito: `fixed bottom-0 right-0 w-80` com fundo semi-transparente escuro
   - Botão toggle para expandir/colapsar (estado local `isOpen`)
   - **Seção "Injetar Evento":**
     - Select com tipos de evento disponíveis para injeção manual: `route_blocked`, `machine_breakdown`, `demand_spike`, `regional_storm`, `trucker_strike`, `truck_breakdown`, `demand_zero`
     - Campos de payload dinâmicos por tipo selecionado:
       - `route_blocked`: input `highway` (string) + `duration_ticks` (number)
       - `machine_breakdown`: select `entity_id` (fábricas do store) + `duration_ticks`
       - `demand_spike`: select `entity_id` (lojas do store) + `multiplier` (number, default 3) + `duration_ticks`
       - `regional_storm`: input `region` (string) + `duration_ticks`
       - `trucker_strike`: `duration_ticks`
       - `truck_breakdown`: select `entity_id` (caminhões do store)
       - `demand_zero`: select `entity_id` (lojas do store) + `duration_ticks`
     - Botão "Injetar" — chama `injectChaosEvent()` com payload montado
   - **Seção "Eventos Ativos":**
     - Listar `worldStore.activeEvents`
     - Cada evento: `event_type`, badge de source (`[User]` em azul, `[MasterAgent]` em roxo, `[Engine]` em cinza), tick de início
     - Botão "Resolver" em cada evento — chama `resolveChaosEvent(event.event_id)`

---

### Grupo 6 — WorldManagement (um agente)

**Tarefa:** Implementar o painel de gestão do mundo (CRUD de materiais e entidades).

Ler antes: `frontend/src/lib/api.ts` (do Grupo 1), `frontend/src/store/worldStore.ts`, `frontend/src/types/world.ts`, design.md §2 (endpoints de entidades e materiais).

1. Implementar `frontend/src/hud/WorldManagement.tsx`:
   - Botão flutuante no HUD (ex: ícone de engrenagem) que abre um `Dialog` fullscreen ou largura grande (shadcn `Dialog`)
   - Navegação por abas dentro do dialog: **Materiais**, **Fábricas**, **Armazéns**, **Lojas**, **Caminhões**, **Estoque**

2. **Aba Materiais:**
   - Ao abrir: carregar materiais via `listMaterials()`
   - Tabela com colunas: ID, Nome, Ativo (badge), Ações
   - Formulário de criação: input `name` → `createMaterial({ name })`
   - Botão "Editar" inline: abre input para alterar nome → `updateMaterial(id, { name })`
   - Botão "Desativar" → `deactivateMaterial(id)` (exibir erro se houver entidades vinculadas)

3. **Aba Fábricas:**
   - Lista de fábricas do store com nome, status, localização
   - Formulário de criação em sub-dialog:
     - Inputs: `id` (slug), `name`, `lat`, `lng`
     - Multi-select de materiais produzidos (carregados de `listMaterials(activeOnly=true)`)
     - Para cada material selecionado: inputs dinâmicos de `stock`, `stock_max`, `production_rate_max`, `production_rate_current`
     - Botão "Criar" → `createFactory(data)`
   - Botão "Deletar" por fábrica → `deleteFactory(id)` com confirmação

4. **Aba Armazéns:**
   - Lista de armazéns do store
   - Formulário de criação:
     - Inputs: `id`, `name`, `lat`, `lng`, `region`, `capacity_total`
     - Multi-select de materiais aceitos
     - Para cada material: inputs de `stock`, `min_stock`
     - Botão "Criar" → `createWarehouse(data)`
   - Botão "Deletar" → `deleteWarehouse(id)` com confirmação

5. **Aba Lojas:**
   - Lista de lojas do store
   - Formulário de criação:
     - Inputs: `id`, `name`, `lat`, `lng`
     - Multi-select de materiais vendidos
     - Para cada material: inputs de `stock`, `demand_rate`, `reorder_point`
     - Botão "Criar" → `createStore(data)`
   - Botão "Deletar" → `deleteStore(id)` com confirmação

6. **Aba Caminhões:**
   - Lista de caminhões do store com tipo, capacidade, status, degradação
   - Formulário de criação:
     - Inputs: `id`, `truck_type` (select: proprietário/terceiro), `capacity_tons`, `base_lat`, `base_lng`
     - Se proprietário: select `factory_id` (fábricas do store)
     - Botão "Criar" → `createTruck(data)`
   - Botão "Deletar" → `deleteTruck(id)` com confirmação

7. **Aba Estoque:**
   - Select de tipo de entidade (factory/warehouse/store)
   - Select de entidade (filtrado pelo tipo)
   - Select de material (filtrado pelos materiais da entidade)
   - Input `delta` (positivo = adicionar, negativo = remover)
   - Botão "Ajustar" → `adjustStock(entityType, id, materialId, delta)`

---

### Grupo 7 — Integração no App.tsx + Validação (sequencial, após todos os grupos)

**Tarefa:** Integrar todos os componentes HUD no layout e validar o conjunto.

1. Editar `frontend/src/App.tsx`:
   - Importar e renderizar todos os componentes HUD dentro do container existente
   - Estrutura:
     ```tsx
     <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden" }}>
       <WorldMap />
       <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
         <StatsBar />
         <InspectPanel />
         <AgentLog />
         <ChaosPanel />
         <WorldManagement />
       </div>
     </div>
     ```
   - Cada componente HUD define `pointer-events: auto` no seu próprio container

2. Rodar `npx tsc --noEmit` em `frontend/` e confirmar zero erros

3. Verificar que todos os componentes renderizam sem crash com store vazio (antes do primeiro tick)

4. Verificar que clique no mapa (entidade) abre o InspectPanel e clique em área vazia fecha

Se alguma verificação falhar, corrigir e rodar novamente.

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
`npx tsc --noEmit` passa com zero erros.
Todos os componentes HUD renderizam sobrepostos ao mapa sem obstruir interação com deck.gl.
Atualizar `state.md`: setar o status da feature `18` para `done`.
