import { create } from "zustand";
import type {
  ActiveRoute,
  FactorySnapshot,
  WarehouseSnapshot,
  StoreSnapshot,
  TruckSnapshot,
  EventPayload,
  AgentDecisionPayload,
  WorldStatePayload,
} from "../types/world";

export interface WorldStoreState {
  tick: number;
  simulatedTimestamp: string;
  factories: FactorySnapshot[];
  warehouses: WarehouseSnapshot[];
  stores: StoreSnapshot[];
  trucks: TruckSnapshot[];
  activeRoutes: ActiveRoute[];
  activeEvents: EventPayload[];
  recentDecisions: AgentDecisionPayload[];
  isConnected: boolean;

  setWorldState: (payload: WorldStatePayload) => void;
  addDecision: (payload: AgentDecisionPayload) => void;
  updateEvent: (payload: EventPayload) => void;
  setConnected: (connected: boolean) => void;
}

export const useWorldStore = create<WorldStoreState>((set) => ({
  tick: 0,
  simulatedTimestamp: "",
  factories: [],
  warehouses: [],
  stores: [],
  trucks: [],
  activeRoutes: [],
  activeEvents: [],
  recentDecisions: [],
  isConnected: false,

  setWorldState: (payload) =>
    set({
      tick: payload.tick,
      simulatedTimestamp: payload.simulated_timestamp,
      factories: payload.factories,
      warehouses: payload.warehouses,
      stores: payload.stores,
      trucks: payload.trucks,
      activeRoutes: payload.active_routes ?? [],
      activeEvents: payload.active_events.map((e) => ({
        event_id: e.event_id,
        event_type: e.event_type,
        source: e.source,
        entity_type: e.entity_type ?? undefined,
        entity_id: e.entity_id ?? undefined,
        status: e.status,
        tick: e.tick,
        description: e.description,
      })),
    }),

  addDecision: (payload) =>
    set((state) => {
      const updated = [payload, ...state.recentDecisions];
      return { recentDecisions: updated.length > 100 ? updated.slice(0, 100) : updated };
    }),

  updateEvent: (payload) =>
    set((state) => {
      if (payload.status === "resolved") {
        return {
          activeEvents: state.activeEvents.filter((e) => e.event_id !== payload.event_id),
        };
      }

      const index = state.activeEvents.findIndex((e) => e.event_id === payload.event_id);
      if (index >= 0) {
        const updated = [...state.activeEvents];
        updated[index] = payload;
        return { activeEvents: updated };
      }

      return { activeEvents: [...state.activeEvents, payload] };
    }),

  setConnected: (connected) => set({ isConnected: connected }),
}));
