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
  region: string;
}

export interface StoreResponse {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: string;
  region: string;
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
  name: string;
  truck_type: string;
  status: string;
  degradation: number;
  lat: number;
  lng: number;
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
