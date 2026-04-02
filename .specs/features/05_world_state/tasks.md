# Tasks — Feature 05: World State

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:

- `CLAUDE.md` — estrutura de pastas §3 (`world/`), decisões arquiteturais §4.1 (WorldState imutável, materiais como catálogo, degradação de caminhões, gatilhos preditivos), convenções §8, TDD §9
- `.specs/features/05_world_state/specs.md` — critérios de aceitação e campos exatos de cada modelo
- `.specs/prd.md` §2 (definição de tick), §3 (catálogo de materiais), §4 (mundo padrão — referência para entender os campos) e §5 (atores do mundo — comportamento dos caminhões, gatilhos preditivos)
- `.specs/design.md` §1 — schema das tabelas (referência para alinhar nomes de campos com o banco)

Não leia specs de outras features. Esta feature não acessa banco nem implementa services.

---

## Plano de Execução

**Grupo 1** é a fase de testes (TDD obrigatório) — roda isolado e para ao terminar.
**Grupos 2 e 3** rodam em paralelo após aprovação dos testes pelo usuário.
**Grupo 4** é sequencial — roda após os Grupos 2 e 3 concluírem, pois `WorldState` depende de todos os entity models definidos.

---

### Grupo 1 — Testes (um agente) ⚠ FASE 1 — PARAR AO CONCLUIR

**Tarefa:** Escrever todos os testes unitários da feature. Não implementar nada de produção.

1. Criar `backend/tests/__init__.py` e `backend/tests/unit/__init__.py` se ainda não existirem

2. Criar `backend/tests/unit/test_physics.py`:
   - Importar apenas de `backend.src.world.physics` (módulo que ainda não existe — os testes vão falhar por `ImportError` até a implementação)
   - Caso `calculate_distance_km`: Campinas (`-22.9056, -47.0608`) → Sorocaba (`-23.5015, -47.4526`) deve retornar entre 90 km e 110 km
   - Caso `calculate_eta_ticks`: distância 120 km, velocidade 60 km/h → 2 ticks; distância 50 km, velocidade 60 km/h → 1 tick (ceil); distância 0 km → 1 tick (mínimo)
   - Caso `calculate_degradation_delta`: carga = capacidade (100%) deve retornar delta maior que carga = 50% para mesma distância; distância zero retorna 0.0
   - Caso `calculate_breakdown_risk`: `degradation=0.0` retorna valor próximo de 0; `degradation=0.5` < `degradation=0.8`; `degradation=0.95` < `degradation=1.0`; `degradation=1.0` retorna `1.0`; todos os retornos estão em `[0.0, 1.0]`
   - Caso `is_trip_blocked`: `0.94` → `False`; `0.95` → `True`; `1.0` → `True`
   - Caso `calculate_maintenance_ticks`: `degradation=0.0` → `2`; `degradation=1.0` → `24`; `degradation=0.5` está entre 2 e 24
   - Caso `evaluate_replenishment_trigger`: `stock=50, min_stock=20, demand_rate=5, lead_time_ticks=6` → dispara (30/5=6 < 9); `stock=100, min_stock=20, demand_rate=5, lead_time_ticks=6` → não dispara (16 > 9); `demand_rate=0` → sempre `False`

3. Criar `backend/tests/unit/test_world_state.py`:
   - Importar de `backend.src.world.state`, `backend.src.world.entities.material`, etc.
   - Construção com todas as entidades: criar instâncias de `Material`, `Factory`, `Warehouse`, `Store`, `Truck` com campos válidos e montar um `WorldState` — deve ser construído sem erro
   - Construção com listas vazias: `WorldState(tick=0, simulated_timestamp=datetime.now(), materials=[], factories=[], warehouses=[], stores=[], trucks=[])` deve ser válido
   - Imutabilidade: tentar atribuir `world_state.tick = 99` deve levantar exceção (`ValidationError` ou `TypeError`)
   - `Truck` com `truck_type="proprietario"` e `factory_id` populado é válido; com `truck_type="terceiro"` e `factory_id=None` é válido

**Parar aqui. Não implementar código de produção. Aguardar aprovação do usuário antes de continuar.**

---

### Grupo 2 — Entity Models (um agente) — roda após aprovação dos testes

**Tarefa:** Implementar todos os modelos Pydantic em `world/entities/`.

1. Criar `backend/src/world/__init__.py` e `backend/src/world/entities/__init__.py` se ainda não existirem

2. Criar `backend/src/world/entities/material.py`:
   - Classe `Material(BaseModel)` com campos: `id: str`, `name: str`, `is_active: bool`

3. Criar `backend/src/world/entities/factory.py`:
   - Classe `FactoryProduct(BaseModel)`: `stock: float`, `stock_reserved: float`, `stock_max: float`, `production_rate_max: float`, `production_rate_current: float`
   - Classe `FactoryPartnerWarehouse(BaseModel)`: `warehouse_id: str`, `priority: int`
   - Classe `Factory(BaseModel)`: `id: str`, `name: str`, `lat: float`, `lng: float`, `status: Literal["operating", "stopped", "reduced_capacity"]`, `products: Dict[str, FactoryProduct]`, `partner_warehouses: List[FactoryPartnerWarehouse]`

4. Criar `backend/src/world/entities/warehouse.py`:
   - Classe `WarehouseStock(BaseModel)`: `stock: float`, `stock_reserved: float`, `min_stock: float`
   - Classe `Warehouse(BaseModel)`: `id: str`, `name: str`, `lat: float`, `lng: float`, `region: str`, `capacity_total: float`, `status: Literal["operating", "rationing", "offline"]`, `stocks: Dict[str, WarehouseStock]`

5. Criar `backend/src/world/entities/store.py`:
   - Classe `StoreStock(BaseModel)`: `stock: float`, `demand_rate: float`, `reorder_point: float`
   - Classe `Store(BaseModel)`: `id: str`, `name: str`, `lat: float`, `lng: float`, `status: Literal["open", "demand_paused", "offline"]`, `stocks: Dict[str, StoreStock]`

6. Criar `backend/src/world/entities/truck.py`:
   - Classe `TruckCargo(BaseModel)`: `material_id: str`, `quantity_tons: float`, `origin_type: str`, `origin_id: str`, `destination_type: str`, `destination_id: str`
   - Classe `TruckRoute(BaseModel)`: `route_id: str`, `path: List[List[float]]`, `timestamps: List[int]`, `eta_ticks: int`
   - Classe `Truck(BaseModel)`: `id: str`, `truck_type: Literal["proprietario", "terceiro"]`, `capacity_tons: float`, `base_lat: float`, `base_lng: float`, `current_lat: float`, `current_lng: float`, `degradation: float`, `breakdown_risk: float`, `status: Literal["idle", "evaluating", "in_transit", "broken", "maintenance"]`, `factory_id: Optional[str] = None`, `cargo: Optional[TruckCargo] = None`, `active_route: Optional[TruckRoute] = None`

---

### Grupo 3 — Physics (um agente) — roda após aprovação dos testes, em paralelo com Grupo 2

**Tarefa:** Implementar todas as funções de cálculo determinístico em `world/physics.py`.

1. Criar `backend/src/world/physics.py` com as funções abaixo. Sem imports de LangGraph, OpenAI, SQLAlchemy ou qualquer I/O. Apenas Python puro + `math`.

2. `calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) → float`:
   - Fórmula haversine. Raio da Terra: 6371 km.

3. `calculate_eta_ticks(distance_km: float, avg_speed_kmh: float = 60.0) → int`:
   - `ceil(distance_km / avg_speed_kmh)`, mínimo 1.

4. `calculate_degradation_delta(distance_km: float, cargo_tons: float, capacity_tons: float) → float`:
   - `(distance_km / 1000) * (0.01 + 0.04 * (cargo_tons / capacity_tons))`
   - Retorna 0.0 se `distance_km == 0` ou `capacity_tons == 0`.

5. `calculate_breakdown_risk(degradation: float) → float`:
   - Para `degradation <= 0.70`: risco linear `degradation * 0.1` (máximo 0.07 nessa zona)
   - Para `degradation > 0.70`: risco exponencial `0.07 + (degradation - 0.70) ** 2 * 3.1` (calibrado para retornar ~1.0 em `degradation=1.0`)
   - Clamp final: `min(1.0, max(0.0, resultado))`

6. `is_trip_blocked(degradation: float) → bool`:
   - `return degradation >= 0.95`

7. `calculate_maintenance_ticks(degradation: float) → int`:
   - `round(2 + degradation * 22)` — retorna 2 quando `degradation=0.0`, 24 quando `degradation=1.0`

8. `evaluate_replenishment_trigger(stock: float, min_stock: float, demand_rate: float, lead_time_ticks: int, safety_factor: float = 1.5) → bool`:
   - Retorna `False` se `demand_rate <= 0`
   - Retorna `(stock - min_stock) / demand_rate < lead_time_ticks * safety_factor`

---

### Grupo 4 — WorldState (um agente, sequencial após Grupos 2 e 3)

**Tarefa:** Implementar `world/state.py` após os entity models existirem.

1. Criar `backend/src/world/state.py`:
   - Importar todos os entity models de `world/entities/`
   - Classe `WorldState(BaseModel)`:
     - `model_config = ConfigDict(frozen=True)`
     - `tick: int`
     - `simulated_timestamp: datetime`
     - `materials: List[Material]`
     - `factories: List[Factory]`
     - `warehouses: List[Warehouse]`
     - `stores: List[Store]`
     - `trucks: List[Truck]`

2. Rodar `pytest backend/tests/unit/test_world_state.py backend/tests/unit/test_physics.py -v` e confirmar que todos os testes passam.

3. Se algum teste falhar, corrigir a implementação antes de prosseguir.

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
`pytest backend/tests/unit/test_physics.py backend/tests/unit/test_world_state.py` passa com zero falhas.
Atualizar `state.md`: setar o status da feature `05` para `done`.
