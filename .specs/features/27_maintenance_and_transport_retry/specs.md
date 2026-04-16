# Feature 27 — Maintenance Completion & Transport Retry

## Objetivo

Resolve dois gaps que travam o ciclo principal da simulacao: caminhoes que entram em manutencao e nunca saem, e ordens confirmadas que ficam sem transporte quando nenhum caminhao esta disponivel.

### Problema 1: Manutencao sem fim

`TruckService.schedule_maintenance()` seta status `maintenance`, zera degradacao e publica evento com `duration_ticks`. Mas ninguem conta os ticks. O engine `_apply_physics()` pula caminhoes que nao sao `IN_TRANSIT`. Resultado: o caminhao fica em `maintenance` eternamente, a frota encolhe a cada manutencao ate nao sobrar nenhum caminhao disponivel.

**Impacto:** Apos algumas manutencoes, todos os caminhoes ficam presos. Nenhuma ordem e transportada. O ciclo para.

### Problema 2: Ordens confirmadas sem transporte

Quando `confirm_order` (F24) despacha um caminhao terceiro e nenhum esta `idle`:
- Nenhum evento `contract_proposal` e criado
- A ordem fica `confirmed` com estoque reservado no armazem
- Ninguem reavalia no proximo tick

Mesma situacao quando `refuse_contract` (F24) tenta achar outro caminhao e nao encontra. A ordem fica encalhada, estoque reservado, sem transporte. Isso tambem afeta `send_stock` da fabrica quando nenhum caminhao proprietario ou terceiro esta disponivel.

**Impacto:** Estoque fica reservado indefinidamente sem sair do lugar. Armazens ficam com capacidade reduzida. Lojas nunca recebem.

### Solucao

Dois mecanismos no engine, ambos deterministicos (sem IA), executados a cada tick em `_apply_physics()`:

1. **Maintenance countdown:** Para cada caminhao em `maintenance`, verificar se `current_tick - maintenance_start_tick >= duration_ticks`. Se sim, transicionar pra `idle`.
2. **Transport retry sweep:** Para cada PendingOrder com status `confirmed` que nao tem rota ativa associada, tentar despachar um caminhao disponivel. Se encontrar, criar evento `contract_proposal` (terceiro) ou `new_order` (proprietario).

---

## Criterios de Aceitacao

### Backend — Manutencao: Tracking de duracao

- [ ] `Truck` ORM model ganha dois campos: `maintenance_start_tick` (`Integer`, nullable) e `maintenance_duration_ticks` (`Integer`, nullable)
- [ ] `TruckService.schedule_maintenance()` atualizado para gravar `maintenance_start_tick = current_tick` e `maintenance_duration_ticks = duration` no caminhao (alem de setar status e zerar degradacao)
- [ ] `TruckRepository` ganha metodo `set_maintenance_info(truck_id, start_tick, duration_ticks)` e `clear_maintenance_info(truck_id)` (seta ambos para None)
- [ ] Alembic migration para adicionar as duas colunas

### Backend — Manutencao: Completion no engine

- [ ] `SimulationEngine._apply_physics()` ganha bloco de manutencao: para cada caminhao com `status == "maintenance"`:
  - Se `maintenance_start_tick` e `maintenance_duration_ticks` sao NOT NULL e `current_tick - maintenance_start_tick >= maintenance_duration_ticks`:
    - Seta status para `idle`
    - Limpa `maintenance_start_tick` e `maintenance_duration_ticks` (set None)
    - Cria evento `truck_maintenance_completed` (via EventRepository) com `entity_type="truck"`, `entity_id=truck.id` para que o TruckAgent acorde e decida proximo passo
  - Se `maintenance_start_tick` e NULL (manutencao legada sem tracking): log warning e seta status `idle` imediatamente (fallback seguro)
- [ ] O bloco de manutencao roda ANTES do bloco de caminhoes em transito (ordem: manutencao → transito → estoques → producao)

### Backend — Transport Retry: Link Route→Order

- [ ] Pre-requisito de F26: `Route` model tem campo `order_id` (FK para PendingOrder). Usado aqui para detectar ordens confirmadas SEM rota.
- [ ] `OrderRepository` ganha metodo `get_confirmed_without_route(limit: int = 10) -> list[PendingOrder]`:
  ```sql
  SELECT po.* FROM pending_orders po
  LEFT JOIN routes r ON r.order_id = po.id AND r.status = 'active'
  WHERE po.status = 'confirmed'
  AND r.id IS NULL
  ORDER BY po.age_ticks DESC
  LIMIT :limit
  ```
  Retorna ordens confirmadas que nao tem nenhuma rota ativa associada. Ordenadas por `age_ticks` DESC (mais antigas primeiro).

### Backend — Transport Retry: Sweep no engine

- [ ] `SimulationEngine._evaluate_triggers()` ganha bloco de transport retry (apos todos os triggers existentes):
  - Chama `OrderRepository.get_confirmed_without_route(limit=10)` — limita a 10 por tick para nao sobrecarregar
  - Para cada ordem retornada:
    - Determina a entidade de origem: se `target_type == "warehouse"` → origem e o warehouse (target_id); se `target_type == "factory"` → origem e a factory (target_id)
    - Busca caminhao disponivel:
      1. Se origem e fabrica: busca proprietario idle da fabrica (`TruckRepository.get_idle_by_factory(factory_id)`)
      2. Se nenhum proprietario ou origem e armazem: busca terceiro idle mais proximo (`TruckRepository.get_nearest_idle_third_party(lat, lng)`)
    - Se encontrar caminhao:
      - Cria evento `new_order` (proprietario) ou `contract_proposal` (terceiro) via `EventRepository.create()` com payload contendo `order_id`, `origin_type`, `origin_id`, `dest_type`, `dest_id`, `material_id`, `quantity_tons`
    - Se nao encontrar: skip — sera reavaliado no proximo tick
  - **Nao criar trigger duplicado:** verificar se ja existe evento ativo para um caminhao referenciando esta ordem (evitar N eventos para a mesma ordem)

### Backend — TruckRepository: Novos metodos de busca

- [ ] `TruckRepository.get_idle_by_factory(factory_id: str) -> Truck | None` — retorna primeiro caminhao com `factory_id` e `status = "idle"`, ou None
- [ ] `TruckRepository.get_nearest_idle_third_party(lat: float, lng: float) -> Truck | None` — retorna caminhao terceiro (`truck_type = "terceiro"`, `status = "idle"`) mais proximo das coordenadas dadas, usando distancia euclidiana entre `current_lat/lng` e o ponto. Retorna None se nenhum disponivel.
- [ ] `TruckRepository.get_all_in_maintenance() -> list[Truck]` — retorna caminhoes com `status = "maintenance"` para o bloco de maintenance completion

### Backend — Integracao com F24

- [ ] `DecisionEffectProcessor._handle_confirm_order()` e `_handle_send_stock()` usam os mesmos metodos de busca de caminhao definidos aqui (`get_idle_by_factory`, `get_nearest_idle_third_party`). Se nao encontrarem caminhao, a ordem fica `confirmed` sem rota — o transport retry sweep pega no proximo tick.
- [ ] `DecisionEffectProcessor._handle_refuse_contract()` tenta achar outro caminhao. Se nao encontrar, o transport retry sweep pega no proximo tick. Nao precisa de logica de retry propria.

### Backend — Events

- [ ] Constante `TRUCK_MAINTENANCE_COMPLETED = "truck_maintenance_completed"` em `events.py`
- [ ] Evento criado pelo engine no bloco de maintenance completion

### Testes

#### Manutencao

- [ ] `test_apply_physics_completes_maintenance_after_duration` — caminhao com `status=maintenance`, `maintenance_start_tick=5`, `maintenance_duration_ticks=8`, `current_tick=13` → status muda para `idle`, maintenance fields limpos
- [ ] `test_apply_physics_does_not_complete_maintenance_early` — caminhao com `maintenance_start_tick=5`, `maintenance_duration_ticks=8`, `current_tick=10` → status permanece `maintenance`
- [ ] `test_apply_physics_creates_maintenance_completed_event` — ao completar manutencao → `EventRepository.create` chamado com `event_type="truck_maintenance_completed"`
- [ ] `test_apply_physics_handles_legacy_maintenance_without_tracking` — caminhao com `status=maintenance` e `maintenance_start_tick=None` → status muda para `idle` imediatamente (fallback)
- [ ] `test_schedule_maintenance_saves_tracking_fields` — `TruckService.schedule_maintenance()` grava `maintenance_start_tick` e `maintenance_duration_ticks` no caminhao

#### Transport Retry

- [ ] `test_get_confirmed_without_route_returns_orphaned_orders` — ordem `confirmed` sem rota ativa → retornada. Ordem `confirmed` com rota ativa → nao retornada
- [ ] `test_get_confirmed_without_route_orders_by_age` — ordens retornadas em ordem decrescente de `age_ticks`
- [ ] `test_evaluate_triggers_retries_orphaned_order_with_idle_truck` — ordem confirmada sem rota + caminhao terceiro idle → evento `contract_proposal` criado
- [ ] `test_evaluate_triggers_retries_factory_order_with_proprietario` — ordem confirmada de fabrica sem rota + caminhao proprietario idle → evento `new_order` criado
- [ ] `test_evaluate_triggers_skips_retry_when_no_truck_available` — nenhum caminhao idle → nenhum evento criado, sem erro
- [ ] `test_evaluate_triggers_limits_retry_to_10_per_tick` — 15 ordens orfas → apenas 10 processadas
- [ ] `test_evaluate_triggers_no_duplicate_events_for_same_order` — ordem ja tem evento ativo para um caminhao → nao cria outro

---

## Fora do Escopo

- `retry_after_tick` backoff para lojas apos rejeicao — feature futura (nao quebra o ciclo, apenas causa ruido)
- `breakdown_risk` roll — engine calcula risco mas nunca sorteia quebra — feature futura
- Chaos events para fabricas/lojas (machine_breakdown, demand_spike) — feature futura
- Reroute de caminhoes em route_blocked — feature futura
- Dashboard/frontend para visualizar manutencao e retries — feature futura
