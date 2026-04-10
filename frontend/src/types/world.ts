export type TruckType = "proprietario" | "terceiro";

export type TruckStatus = "idle" | "evaluating" | "in_transit" | "broken" | "maintenance";

export type FactoryStatus = "operating" | "stopped" | "reduced_capacity";

export type WarehouseStatus = "operating" | "rationing" | "offline";

export type StoreStatus = "open" | "demand_paused" | "offline";

export type RouteStatus = "active" | "completed" | "interrupted";

export type RouteNodeType = "factory" | "warehouse" | "store";

export type OrderStatus = "pending" | "confirmed" | "rejected" | "delivered" | "cancelled";

export type OrderRequesterType = "store" | "warehouse";

export type OrderTargetType = "warehouse" | "factory";

export type ChaosEventSource = "user" | "master_agent" | "engine";

export type ChaosEventEntityType = "factory" | "warehouse" | "store" | "truck";

export type ChaosEventStatus = "active" | "resolved";

export type AgentType = "factory" | "warehouse" | "store" | "truck" | "master";

export type EntityType = "factory" | "warehouse" | "store" | "truck";

export interface FactoryProductSnapshot {
  material_id: string;
  stock: number;
  stock_reserved: number;
  stock_max: number;
  production_rate_max: number;
  production_rate_current: number;
}

export interface FactorySnapshot {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: FactoryStatus;
  products: FactoryProductSnapshot[];
}

export interface WarehouseStockSnapshot {
  material_id: string;
  stock: number;
  stock_reserved: number;
  min_stock: number;
}

export interface WarehouseSnapshot {
  id: string;
  name: string;
  lat: number;
  lng: number;
  region: string;
  capacity_total: number;
  status: WarehouseStatus;
  stocks: WarehouseStockSnapshot[];
}

export interface StoreStockSnapshot {
  material_id: string;
  stock: number;
  demand_rate: number;
  reorder_point: number;
}

export interface StoreSnapshot {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: StoreStatus;
  stocks: StoreStockSnapshot[];
}

export interface TruckCargo {
  product: string;
  quantity: number;
  origin: string;
  destination: string;
}

export interface TruckSnapshot {
  id: string;
  truck_type: TruckType;
  capacity_tons: number;
  base_lat: number;
  base_lng: number;
  current_lat: number;
  current_lng: number;
  degradation: number;
  breakdown_risk: number;
  status: TruckStatus;
  factory_id: string | null;
  cargo: TruckCargo | null;
  active_route_id: string | null;
}

export interface ActiveRoute {
  id: string;
  truck_id: string;
  origin_type: RouteNodeType;
  origin_id: string;
  dest_type: RouteNodeType;
  dest_id: string;
  path: [number, number][];
  timestamps: number[];
  eta_ticks: number;
  status: RouteStatus;
  started_at: string;
}

export interface ActiveEvent {
  event_id: string;
  event_type: string;
  source: ChaosEventSource;
  entity_type: ChaosEventEntityType | null;
  entity_id: string | null;
  status: ChaosEventStatus;
  tick: number;
  description: string;
}

export interface WorldStatePayload {
  tick: number;
  simulated_timestamp: string;
  factories: FactorySnapshot[];
  warehouses: WarehouseSnapshot[];
  stores: StoreSnapshot[];
  trucks: TruckSnapshot[];
  active_events: ActiveEvent[];
}

export interface AgentDecisionPayload {
  tick: number;
  agent_type: AgentType;
  entity_id: string;
  entity_name: string;
  action: string;
  summary: string;
  reasoning?: string;
}

export interface EventPayload {
  event_id: string;
  event_type: string;
  source: ChaosEventSource;
  entity_type?: ChaosEventEntityType;
  entity_id?: string;
  status: ChaosEventStatus;
  tick: number;
  description: string;
}

export interface WSMessage {
  channel: "world_state" | "agent_decisions" | "events";
  payload: WorldStatePayload | AgentDecisionPayload | EventPayload;
}
