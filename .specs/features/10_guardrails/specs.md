# Feature 10 — Guardrails Pydantic

## Objetivo

Implementar os schemas Pydantic de validação das decisões dos agentes, substituindo os stubs atuais (que aceitam qualquer `action`/`payload`) por schemas completos com `Literal` actions, payloads tipados e validators de negócio. Esta feature é a última barreira entre o output do LLM e o banco de dados — nenhuma decisão afeta o estado do mundo sem passar por esses guardrails.

Após esta feature, o nó `act` do `StateGraph` rejeita decisões malformadas, com ações inválidas, ou que violem constraints de negócio (ex: quantidade > estoque disponível, manutenção prematura, viagem com degradação ≥ 95%).

---

## Critérios de Aceitação

### Backend — `guardrails/base.py`

- [ ] `AgentDecisionBase(BaseModel)` exporta os campos `action: str` e `reasoning_summary: str`
- [ ] `reasoning_summary` é obrigatório e não pode ser string vazia

### Backend — `guardrails/factory.py`

- [ ] `StartProductionPayload` valida `material_id: str` e `quantity_tons: float` com `quantity_tons > 0`
- [ ] `SendStockPayload` valida `material_id: str`, `quantity_tons: float` e `destination_warehouse_id: str` com `quantity_tons > 0`
- [ ] `FactoryDecision` herda de `AgentDecisionBase` com `action: Literal["start_production", "reduce_production", "stop_production", "send_stock", "request_truck", "hold"]`
- [ ] `payload` é `StartProductionPayload | SendStockPayload | None`, obrigatório para `start_production` e `send_stock`, `None` para as demais ações

### Backend — `guardrails/warehouse.py`

- [ ] `RequestResupplyPayload` valida `material_id`, `quantity_tons`, `from_factory_id` com `quantity_tons > 0`
- [ ] `ConfirmOrderPayload` valida `order_id`, `quantity_tons`, `eta_ticks` com `quantity_tons > 0` e `eta_ticks > 0`
- [ ] `RejectOrderPayload` valida `order_id`, `reason: str`, `retry_after_ticks: int` com `retry_after_ticks >= 0`
- [ ] `WarehouseDecision` herda de `AgentDecisionBase` com `action: Literal["request_resupply", "confirm_order", "reject_order", "request_delivery_truck", "ration_stock", "hold"]`
- [ ] `payload` é `RequestResupplyPayload | ConfirmOrderPayload | RejectOrderPayload | None`, obrigatório para `request_resupply`, `confirm_order` e `reject_order`

### Backend — `guardrails/store.py`

- [ ] `OrderReplenishmentPayload` valida `material_id`, `quantity_tons`, `from_warehouse_id` com `quantity_tons > 0`
- [ ] `StoreDecision` herda de `AgentDecisionBase` com `action: Literal["order_replenishment", "order_direct_from_factory", "wait_backoff", "hold"]`
- [ ] `payload` é `OrderReplenishmentPayload | None`, obrigatório para `order_replenishment`

### Backend — `guardrails/truck.py`

- [ ] `AcceptContractPayload` valida `order_id: str` e `chosen_route_risk_level: Literal["low", "medium", "high"]`
- [ ] `RefuseContractPayload` valida `order_id: str` e `reason: Literal["high_degradation", "route_risk", "low_cargo_utilization", "in_maintenance"]`
- [ ] `RequestMaintenancePayload` valida `current_degradation: float` e rejeita valores abaixo de `MAINTENANCE_THRESHOLD` (agente não deve pedir manutenção antes da hora)
- [ ] `TruckDecision` herda de `AgentDecisionBase` com `action: Literal["accept_contract", "refuse_contract", "choose_route", "request_maintenance", "alert_breakdown", "complete_delivery"]`
- [ ] `payload` é `AcceptContractPayload | RefuseContractPayload | RequestMaintenancePayload | None`
- [ ] Validator de nível de decisão: se `degradation >= 0.95` e `action` não é `request_maintenance`, a decisão é rejeitada (guardrail do engine)

### Backend — `guardrails/__init__.py`

- [ ] Re-exporta `AgentDecisionBase`, `FactoryDecision`, `WarehouseDecision`, `StoreDecision`, `TruckDecision` e todos os payloads

### Backend — Testes Unitários

- [ ] Testes em `backend/tests/unit/guardrails/` espelhando a estrutura `src/guardrails/`
- [ ] Cada decision class tem testes para: criação válida, ação inválida rejeitada, payload obrigatório ausente rejeitado, validators de campo (quantidade negativa, degradação fora de range)
- [ ] `TruckDecision` tem teste específico para o guardrail de `degradation >= 0.95`
- [ ] `RequestMaintenancePayload` tem teste para rejeição abaixo do threshold de manutenção
- [ ] Todos os testes passam com `pytest backend/tests/unit/guardrails/`

---

## Fora do Escopo

- Validação contra `WorldState` real (ex: verificar se `from_factory_id` existe no banco) — será feita na camada de services (feature 06 já implementa parte disso; validação cross-entity é responsabilidade do nó `act` quando integrado com dados reais)
- Alterações no nó `act` de `agents/base.py` — a integração dos novos schemas no grafo já funciona via `schema_class(**raw)` existente; esta feature apenas substitui os stubs
- System prompts dos agentes (feature 09)
- Tools dos agentes (feature 11)
