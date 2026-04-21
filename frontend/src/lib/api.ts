const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/v1${path}`;
  const headers: Record<string, string> = {};

  if (options?.body) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, { ...options, headers: { ...headers, ...options?.headers } });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }

  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as unknown as T);
}

// --- World Snapshot ---

import type {
  WorldStatePayload,
  FactorySnapshot,
  WarehouseSnapshot,
  StoreSnapshot,
  TruckSnapshot,
} from "@/types/world";

interface RawSnapshot {
  tick: number;
  simulated_timestamp: string;
  factories: Array<Record<string, unknown>>;
  warehouses: Array<Record<string, unknown>>;
  stores: Array<Record<string, unknown>>;
  trucks: TruckSnapshot[];
  active_events?: unknown[];
  active_routes?: unknown[];
}

function dictToArray<T>(dict: Record<string, T>, keyName: string): (T & Record<string, string>)[] {
  return Object.entries(dict).map(([key, value]) => ({
    ...value,
    [keyName]: key,
  }));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function normalizeWorldState(raw: any): WorldStatePayload {
  return transformSnapshot(raw as RawSnapshot);
}

function transformSnapshot(raw: RawSnapshot): WorldStatePayload {
  const factories: FactorySnapshot[] = raw.factories.map((f) => ({
    id: f.id as string,
    name: f.name as string,
    lat: f.lat as number,
    lng: f.lng as number,
    status: f.status as FactorySnapshot["status"],
    products: Array.isArray(f.products)
      ? f.products
      : dictToArray(f.products as Record<string, unknown>, "material_id"),
  }));

  const warehouses: WarehouseSnapshot[] = raw.warehouses.map((w) => ({
    id: w.id as string,
    name: w.name as string,
    lat: w.lat as number,
    lng: w.lng as number,
    region: w.region as string,
    capacity_total: w.capacity_total as number,
    status: w.status as WarehouseSnapshot["status"],
    stocks: Array.isArray(w.stocks)
      ? w.stocks
      : dictToArray(w.stocks as Record<string, unknown>, "material_id"),
  }));

  const stores: StoreSnapshot[] = raw.stores.map((s) => ({
    id: s.id as string,
    name: s.name as string,
    lat: s.lat as number,
    lng: s.lng as number,
    status: s.status as StoreSnapshot["status"],
    stocks: Array.isArray(s.stocks)
      ? s.stocks
      : dictToArray(s.stocks as Record<string, unknown>, "material_id"),
  }));

  return {
    tick: raw.tick,
    simulated_timestamp: raw.simulated_timestamp,
    factories,
    warehouses,
    stores,
    trucks: raw.trucks,
    active_events: (raw.active_events as WorldStatePayload["active_events"]) ?? [],
    active_routes: (raw.active_routes as WorldStatePayload["active_routes"]) ?? [],
  };
}

export function fetchWorldSnapshot(): Promise<WorldStatePayload> {
  return apiFetch<RawSnapshot>("/world/snapshot").then(transformSnapshot);
}

// --- Simulation ---

export interface SimulationStatus {
  status: "running" | "stopped";
  tick: number;
  tick_interval_seconds: number;
}

export function getSimulationStatus(): Promise<SimulationStatus> {
  return apiFetch<SimulationStatus>("/simulation/status");
}

export function startSimulation(): Promise<void> {
  return apiFetch("/simulation/start", { method: "POST" });
}

export function stopSimulation(): Promise<void> {
  return apiFetch("/simulation/stop", { method: "POST" });
}

export function advanceTick(): Promise<void> {
  return apiFetch("/simulation/tick", { method: "POST" });
}

export function setSimulationSpeed(seconds: number): Promise<void> {
  return apiFetch("/simulation/speed", {
    method: "PATCH",
    body: JSON.stringify({ tick_interval_seconds: seconds }),
  });
}

// --- Chaos ---

export interface ChaosEventCreate {
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload?: Record<string, unknown>;
}

export interface ChaosEventResponse {
  id: string;
  event_type: string;
  source: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  status: string;
  tick_start: number;
  tick_end: number | null;
}

export function injectChaosEvent(data: ChaosEventCreate, currentTick: number): Promise<ChaosEventResponse> {
  return apiFetch<ChaosEventResponse>(`/chaos/events?current_tick=${currentTick}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function resolveChaosEvent(eventId: string, currentTick: number): Promise<ChaosEventResponse> {
  return apiFetch<ChaosEventResponse>(`/chaos/events/${eventId}/resolve?current_tick=${currentTick}`, {
    method: "POST",
  });
}

// --- Materials ---

export interface MaterialCreate {
  name: string;
}

export interface MaterialUpdate {
  name: string;
}

export interface MaterialResponse {
  id: string;
  name: string;
  is_active: boolean;
}

export function listMaterials(activeOnly = false): Promise<MaterialResponse[]> {
  const query = activeOnly ? "?active_only=true" : "";
  return apiFetch<MaterialResponse[]>(`/materials${query}`);
}

export function createMaterial(data: MaterialCreate): Promise<MaterialResponse> {
  return apiFetch<MaterialResponse>("/materials", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateMaterial(id: string, data: MaterialUpdate): Promise<MaterialResponse> {
  return apiFetch<MaterialResponse>(`/materials/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deactivateMaterial(id: string): Promise<MaterialResponse> {
  return apiFetch<MaterialResponse>(`/materials/${id}/deactivate`, { method: "PATCH" });
}

// --- Factories ---

export interface FactoryCreate {
  name: string;
  lat: number;
  lng: number;
}

export interface FactoryResponse {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: string;
}

export function createFactory(data: FactoryCreate): Promise<FactoryResponse> {
  return apiFetch<FactoryResponse>("/entities/factories", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteFactory(id: string): Promise<void> {
  return apiFetch(`/entities/factories/${id}`, { method: "DELETE" });
}

// --- Warehouses ---

export interface WarehouseCreate {
  name: string;
  lat: number;
  lng: number;
  region: string;
  capacity_total: number;
}

export interface WarehouseResponse {
  id: string;
  name: string;
  lat: number;
  lng: number;
  region: string;
  capacity_total: number;
  status: string;
}

export function createWarehouse(data: WarehouseCreate): Promise<WarehouseResponse> {
  return apiFetch<WarehouseResponse>("/entities/warehouses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteWarehouse(id: string): Promise<void> {
  return apiFetch(`/entities/warehouses/${id}`, { method: "DELETE" });
}

// --- Stores ---

export interface StoreCreate {
  name: string;
  lat: number;
  lng: number;
}

export interface StoreResponse {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: string;
}

export function createStore(data: StoreCreate): Promise<StoreResponse> {
  return apiFetch<StoreResponse>("/entities/stores", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteStore(id: string): Promise<void> {
  return apiFetch(`/entities/stores/${id}`, { method: "DELETE" });
}

// --- Trucks ---

export interface TruckCreate {
  name: string;
  truck_type: string;
  lat: number;
  lng: number;
}

export interface TruckResponse {
  id: string;
  truck_type: string;
  capacity_tons: number;
  status: string;
  degradation: number;
  current_lat: number;
  current_lng: number;
  factory_id: string | null;
}

export function createTruck(data: TruckCreate): Promise<TruckResponse> {
  return apiFetch<TruckResponse>("/entities/trucks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteTruck(id: string): Promise<void> {
  return apiFetch(`/entities/trucks/${id}`, { method: "DELETE" });
}

// --- Stock Adjustment ---

export interface StockAdjust {
  material_id: string;
  delta: number;
}

export function adjustStock(entityType: string, id: string, data: StockAdjust): Promise<void> {
  return apiFetch(`/entities/${entityType}/${id}/stock`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
