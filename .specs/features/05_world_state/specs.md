# Feature 05 — World State

## Objetivo

Implementar a camada de domínio pura do Gêmeo Digital: os modelos Pydantic que representam o estado em memória de cada entidade do mundo (`Material`, `Factory`, `Warehouse`, `Store`, `Truck`) e o snapshot imutável `WorldState` que os agrega. Também cobre `physics.py` — as funções determinísticas de distância, ETA, degradação e avaliação de gatilhos preditivos.

Esta feature não acessa banco de dados. Ela define os tipos que todo o sistema usa: o engine de simulação (feature 07), os agentes (feature 08–09), os guardrails (feature 10) e o `WorldStateService` (feature 06) dependem diretamente dos modelos e funções definidos aqui.

---

## Critérios de Aceitação

### Modelos de Domínio — `world/entities/`

- [ ] `world/entities/material.py` exporta `Material` com campos: `id: str`, `name: str`, `is_active: bool`
- [ ] `world/entities/factory.py` exporta `FactoryProduct` (campos: `stock: float`, `stock_reserved: float`, `stock_max: float`, `production_rate_max: float`, `production_rate_current: float`), `FactoryPartnerWarehouse` (campos: `warehouse_id: str`, `priority: int`) e `Factory` (campos: `id: str`, `name: str`, `lat: float`, `lng: float`, `status: Literal["operating", "stopped", "reduced_capacity"]`, `products: Dict[str, FactoryProduct]`, `partner_warehouses: List[FactoryPartnerWarehouse]`)
- [ ] `world/entities/warehouse.py` exporta `WarehouseStock` (campos: `stock: float`, `stock_reserved: float`, `min_stock: float`) e `Warehouse` (campos: `id: str`, `name: str`, `lat: float`, `lng: float`, `region: str`, `capacity_total: float`, `status: Literal["operating", "rationing", "offline"]`, `stocks: Dict[str, WarehouseStock]`)
- [ ] `world/entities/store.py` exporta `StoreStock` (campos: `stock: float`, `demand_rate: float`, `reorder_point: float`) e `Store` (campos: `id: str`, `name: str`, `lat: float`, `lng: float`, `status: Literal["open", "demand_paused", "offline"]`, `stocks: Dict[str, StoreStock]`)
- [ ] `world/entities/truck.py` exporta `TruckCargo` (campos: `material_id: str`, `quantity_tons: float`, `origin_type: str`, `origin_id: str`, `destination_type: str`, `destination_id: str`), `TruckRoute` (campos: `route_id: str`, `path: List[List[float]]`, `timestamps: List[int]]`, `eta_ticks: int`) e `Truck` (campos: `id: str`, `truck_type: Literal["proprietario", "terceiro"]`, `capacity_tons: float`, `base_lat: float`, `base_lng: float`, `current_lat: float`, `current_lng: float`, `degradation: float`, `breakdown_risk: float`, `status: Literal["idle", "evaluating", "in_transit", "broken", "maintenance"]`, `factory_id: Optional[str]`, `cargo: Optional[TruckCargo]`, `active_route: Optional[TruckRoute]`)
- [ ] Todos os modelos são Pydantic v2 (`BaseModel`) — nenhum usa `dataclass` ou `TypedDict`
- [ ] Campos `Dict[str, ...]` usam `str` como chave (o `material_id` do catálogo)

### WorldState — `world/state.py`

- [ ] `world/state.py` exporta `WorldState` com campos: `tick: int`, `simulated_timestamp: datetime`, `materials: List[Material]`, `factories: List[Factory]`, `warehouses: List[Warehouse]`, `stores: List[Store]`, `trucks: List[Truck]`
- [ ] `WorldState` é um Pydantic `BaseModel` — imutável via `model_config = ConfigDict(frozen=True)`
- [ ] Um `WorldState` construído a partir de listas vazias é válido (zero entidades é estado legítimo)

### Physics — `world/physics.py`

- [ ] `calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) → float` retorna distância em km pela fórmula haversine
- [ ] `calculate_eta_ticks(distance_km: float, avg_speed_kmh: float = 60.0) → int` retorna ceil da divisão distância / velocidade, com mínimo de 1 tick
- [ ] `calculate_degradation_delta(distance_km: float, cargo_tons: float, capacity_tons: float) → float` retorna incremento proporcional à distância e ao percentual de carga (`cargo_tons / capacity_tons`)
- [ ] `calculate_breakdown_risk(degradation: float) → float` retorna valor entre 0.0 e 1.0; para `degradation <= 0.70` o risco é baixo (linear suave); para `degradation > 0.70` o risco cresce exponencialmente; `degradation == 1.0` retorna 1.0
- [ ] `is_trip_blocked(degradation: float) → bool` retorna `True` se `degradation >= 0.95`
- [ ] `calculate_maintenance_ticks(degradation: float) → int` retorna valor no intervalo `[2, 24]` proporcional ao nível de desgaste
- [ ] `evaluate_replenishment_trigger(stock: float, min_stock: float, demand_rate: float, lead_time_ticks: int, safety_factor: float = 1.5) → bool` retorna `True` quando `(stock - min_stock) / demand_rate < lead_time_ticks * safety_factor`; retorna `False` se `demand_rate == 0` (sem consumo, sem gatilho)

### Testes — `tests/unit/`

- [ ] `tests/unit/test_physics.py` cobre todos os casos de `physics.py`:
  - Haversine entre duas coordenadas reais do estado de SP (ex: Campinas → Sorocaba ≈ 100 km)
  - ETA com velocidade padrão e com velocidade customizada; arredondamento para cima; mínimo 1 tick
  - Degradação delta: carga completa gera delta maior que carga parcial para a mesma distância
  - Breakdown risk: valor em `degradation=0.5` < valor em `degradation=0.8` < valor em `degradation=0.95`; `degradation=1.0` retorna `1.0`
  - `is_trip_blocked`: `False` para `0.94`, `True` para `0.95` e `1.0`
  - Maintenance ticks: `degradation=0.0` retorna `2`, `degradation=1.0` retorna `24`, valores intermediários estão no intervalo
  - Replenishment trigger: dispara quando projeção cruza threshold; não dispara com demanda zero; não dispara com estoque folgado
- [ ] `tests/unit/test_world_state.py` cobre:
  - Construção de `WorldState` com todas as entidades populadas
  - Construção com listas vazias (estado válido)
  - Tentativa de mutação em `WorldState` frozen levanta `ValidationError` ou `TypeError`
- [ ] Todos os testes passam com `pytest`

---

## Fora do Escopo

- Acesso ao banco de dados — nenhuma query SQL nesta feature (repositories: feature 04)
- `WorldStateService.load_world_state()` — método que carrega do PostgreSQL (feature 06)
- Migrations e seed — dados iniciais do mundo (feature 03)
- Guardrails de decisões dos agentes — schemas `FactoryDecision`, `TruckDecision` etc. (feature 10)
- Uso do `WorldState` por agentes LangGraph (features 08–09)
- Lógica de eventos de caos — `ChaosEvent` não é um entity model desta feature (feature 12)
- Modelos ORM SQLAlchemy — estão em `database/models/` (feature 02)
