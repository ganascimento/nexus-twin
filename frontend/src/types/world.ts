export type MaterialId = string;

export type TruckType = "proprietario" | "terceiro";

export type TruckStatus =
  | "idle"
  | "in_transit"
  | "loading"
  | "unloading"
  | "maintenance"
  | "broken_down";

export type EntityStatus = "active" | "inactive" | "maintenance";

export type ChaosEventType =
  | "trucker_strike"
  | "machine_breakdown"
  | "demand_spike"
  | "road_block"
  | "regional_storm"
  | "truck_breakdown"
  | "demand_zero";

export type RouteStatus = "clear" | "congested" | "blocked";

export type AgentActionType =
  | "request_resupply"
  | "confirm_order"
  | "start_production"
  | "send_stock"
  | "order_replenishment"
  | "accept_contract"
  | "refuse_contract"
  | "hold"
  | "emergency_order";

export interface Material {
  id: MaterialId;
  name: string;
  is_active: boolean;
}

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface Factory {
  id: string;
  name: string;
  location: GeoPoint;
  status: EntityStatus;
  products: MaterialId[];
  stock: Record<MaterialId, number>;
  production_rate_max: Record<MaterialId, number>;
  capacity_tons: number;
}

export interface Warehouse {
  id: string;
  name: string;
  location: GeoPoint;
  status: EntityStatus;
  stock: Record<MaterialId, number>;
  min_stock: Record<MaterialId, number>;
  capacity_tons: number;
}

export interface Store {
  id: string;
  name: string;
  location: GeoPoint;
  status: EntityStatus;
  stock: Record<MaterialId, number>;
  demand_rate: Record<MaterialId, number>;
  reorder_point: Record<MaterialId, number>;
}

export interface TruckRoute {
  path: [number, number][];
  timestamps: number[];
  status: RouteStatus;
}

export interface Truck {
  id: string;
  name: string;
  truck_type: TruckType;
  status: TruckStatus;
  location: GeoPoint;
  cargo: Record<MaterialId, number>;
  capacity_tons: number;
  degradation: number;
  breakdown_risk: number;
  route: TruckRoute | null;
  assigned_factory_id: string | null;
}

export interface ChaosEvent {
  id: string;
  event_type: ChaosEventType;
  description: string;
  affected_entity_id: string | null;
  started_at_tick: number;
  resolved_at_tick: number | null;
  is_resolved: boolean;
}

export interface AgentDecision {
  id: string;
  agent_type: string;
  entity_id: string;
  action: AgentActionType;
  payload: Record<string, unknown>;
  tick: number;
  timestamp: string;
}

export interface PendingOrder {
  id: string;
  from_entity_id: string;
  to_entity_id: string;
  material_id: MaterialId;
  quantity_tons: number;
  status: "pending" | "confirmed" | "rejected" | "fulfilled";
  created_at_tick: number;
  age_ticks: number;
}

export interface WorldState {
  tick: number;
  simulated_time: string;
  materials: Material[];
  factories: Factory[];
  warehouses: Warehouse[];
  stores: Store[];
  trucks: Truck[];
  active_chaos_events: ChaosEvent[];
  pending_orders: PendingOrder[];
  recent_decisions: AgentDecision[];
}
