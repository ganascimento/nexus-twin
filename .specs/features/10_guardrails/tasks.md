# Tasks — Feature 10: Guardrails Pydantic

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:
- `CLAUDE.md` — convenções (§8), guardrails first (§9), decisões arquiteturais (§4.2)
- `.specs/features/10_guardrails/specs.md` — critérios de aceitação
- `.specs/design.md` §9 (Guardrails Pydantic) — schemas completos com todos os campos, validators e hierarquia de validação
- `backend/src/agents/base.py` — ver como `act_node` consome os schemas via `schema_class(**raw)` e `DECISION_SCHEMA_MAP`
- `backend/src/guardrails/` — stubs atuais a serem substituídos

---

## Plano de Execução

**Fase 1 (TDD):** Grupo 1 escreve todos os testes. Parada obrigatória para aprovação.

**Fase 2 (Implementação):** Grupos 2–3 rodam em paralelo — sem dependências entre si. Grupo 2 implementa `base.py`, Grupo 3 implementa os 4 guardrails de agente (um único agente cuida dos 4 arquivos, pois são independentes mas pequenos).

---

### Grupo 1 — Testes Unitários (TDD — Fase 1)

**Tarefa:** Criar todos os testes dos guardrails. Parar após criar os testes. Não implementar lógica de produção. Aguardar aprovação do usuário.

1. Criar `backend/tests/unit/guardrails/__init__.py`

2. Criar `backend/tests/unit/guardrails/test_base.py`:
   - Teste que `AgentDecisionBase` aceita `action` + `reasoning_summary` válidos
   - Teste que `reasoning_summary` vazio é rejeitado
   - Teste que `reasoning_summary` ausente é rejeitado

3. Criar `backend/tests/unit/guardrails/test_factory.py`:
   - `StartProductionPayload`: aceita dados válidos; rejeita `quantity_tons <= 0`
   - `SendStockPayload`: aceita dados válidos; rejeita `quantity_tons <= 0`
   - `FactoryDecision`: aceita cada uma das 6 ações válidas com payload correto
   - `FactoryDecision`: rejeita ação fora do `Literal` (ex: `"invalid_action"`)
   - `FactoryDecision`: rejeita `start_production` sem payload
   - `FactoryDecision`: rejeita `send_stock` sem payload
   - `FactoryDecision`: aceita `hold` sem payload

4. Criar `backend/tests/unit/guardrails/test_warehouse.py`:
   - `RequestResupplyPayload`: aceita dados válidos; rejeita `quantity_tons <= 0`
   - `ConfirmOrderPayload`: aceita dados válidos; rejeita `quantity_tons <= 0`; rejeita `eta_ticks <= 0`
   - `RejectOrderPayload`: aceita dados válidos; rejeita `retry_after_ticks < 0`
   - `WarehouseDecision`: aceita cada uma das 6 ações válidas
   - `WarehouseDecision`: rejeita ação inválida
   - `WarehouseDecision`: rejeita `request_resupply` sem payload
   - `WarehouseDecision`: rejeita `confirm_order` sem payload
   - `WarehouseDecision`: rejeita `reject_order` sem payload

5. Criar `backend/tests/unit/guardrails/test_store.py`:
   - `OrderReplenishmentPayload`: aceita dados válidos; rejeita `quantity_tons <= 0`
   - `StoreDecision`: aceita cada uma das 4 ações válidas
   - `StoreDecision`: rejeita ação inválida
   - `StoreDecision`: rejeita `order_replenishment` sem payload
   - `StoreDecision`: aceita `hold` sem payload

6. Criar `backend/tests/unit/guardrails/test_truck.py`:
   - `AcceptContractPayload`: aceita dados válidos; rejeita `chosen_route_risk_level` fora do Literal
   - `RefuseContractPayload`: aceita dados válidos; rejeita `reason` fora do Literal
   - `RequestMaintenancePayload`: aceita `current_degradation` acima do threshold; rejeita abaixo do threshold
   - `TruckDecision`: aceita cada uma das 6 ações válidas
   - `TruckDecision`: rejeita ação inválida
   - **Guardrail de degradação:** `TruckDecision` com `degradation >= 0.95` e `action != "request_maintenance"` é rejeitada
   - **Guardrail de degradação:** `TruckDecision` com `degradation >= 0.95` e `action == "request_maintenance"` é aceita
   - **Guardrail de degradação:** `TruckDecision` com `degradation < 0.95` e `action == "accept_contract"` é aceita

---

### Grupo 2 — `guardrails/base.py` (um agente)

**Tarefa:** Implementar `AgentDecisionBase`.

1. Substituir o conteúdo de `backend/src/guardrails/base.py`:
   - Classe `AgentDecisionBase(BaseModel)` com campos `action: str` e `reasoning_summary: str`
   - `field_validator` em `reasoning_summary` que rejeita string vazia (strip + check)

---

### Grupo 3 — Guardrails dos 4 agentes (um agente)

**Tarefa:** Implementar os schemas dos 4 tipos de agente.

1. Substituir `backend/src/guardrails/factory.py`:
   - `StartProductionPayload(BaseModel)`: `material_id: str`, `quantity_tons: float` com validator `> 0`
   - `SendStockPayload(BaseModel)`: `material_id: str`, `quantity_tons: float`, `destination_warehouse_id: str` com validator `> 0`
   - `FactoryDecision(AgentDecisionBase)`: `action: Literal[...]` com as 6 ações do design.md §9
   - `payload: StartProductionPayload | SendStockPayload | None = None`
   - `model_validator(mode="after")` que exige payload para `start_production` e `send_stock`

2. Substituir `backend/src/guardrails/warehouse.py`:
   - `RequestResupplyPayload(BaseModel)`: `material_id`, `quantity_tons`, `from_factory_id` com validator `> 0` em `quantity_tons`
   - `ConfirmOrderPayload(BaseModel)`: `order_id`, `quantity_tons`, `eta_ticks` com validators `> 0`
   - `RejectOrderPayload(BaseModel)`: `order_id`, `reason: str`, `retry_after_ticks: int` com validator `>= 0`
   - `WarehouseDecision(AgentDecisionBase)`: `action: Literal[...]` com as 6 ações
   - `payload: RequestResupplyPayload | ConfirmOrderPayload | RejectOrderPayload | None = None`
   - `model_validator(mode="after")` que exige payload para `request_resupply`, `confirm_order`, `reject_order`

3. Substituir `backend/src/guardrails/store.py`:
   - `OrderReplenishmentPayload(BaseModel)`: `material_id`, `quantity_tons`, `from_warehouse_id` com validator `> 0`
   - `StoreDecision(AgentDecisionBase)`: `action: Literal[...]` com as 4 ações
   - `payload: OrderReplenishmentPayload | None = None`
   - `model_validator(mode="after")` que exige payload para `order_replenishment`

4. Substituir `backend/src/guardrails/truck.py`:
   - `AcceptContractPayload(BaseModel)`: `order_id: str`, `chosen_route_risk_level: Literal["low", "medium", "high"]`
   - `RefuseContractPayload(BaseModel)`: `order_id: str`, `reason: Literal["high_degradation", "route_risk", "low_cargo_utilization", "in_maintenance"]`
   - `RequestMaintenancePayload(BaseModel)`: `current_degradation: float` com `field_validator` que rejeita valores abaixo de `MAINTENANCE_THRESHOLD` (definir constante no módulo, ex: `0.30`)
   - `TruckDecision(AgentDecisionBase)`: `action: Literal[...]` com as 6 ações, `payload: AcceptContractPayload | RefuseContractPayload | RequestMaintenancePayload | None = None`
   - `model_validator(mode="after")` que verifica: se `payload` é `RequestMaintenancePayload` e `current_degradation >= 0.95`, qualquer `action` que não seja `request_maintenance` é rejeitada. Definir constante `DEGRADATION_BLOCK_THRESHOLD = 0.95`

5. Atualizar `backend/src/guardrails/__init__.py`:
   - Re-exportar `AgentDecisionBase`, `FactoryDecision`, `StartProductionPayload`, `SendStockPayload`, `WarehouseDecision`, `RequestResupplyPayload`, `ConfirmOrderPayload`, `RejectOrderPayload`, `StoreDecision`, `OrderReplenishmentPayload`, `TruckDecision`, `AcceptContractPayload`, `RefuseContractPayload`, `RequestMaintenancePayload`

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos.
Todos os testes passam com `pytest backend/tests/unit/guardrails/ -v`.
Atualizar `state.md`: setar o status da feature `10` para `done`.
