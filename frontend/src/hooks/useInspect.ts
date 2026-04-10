import { create } from "zustand";
import type { EntityType } from "../types/world";

export interface InspectState {
  selectedEntityId: string | null;
  selectedEntityType: EntityType | null;
  selectEntity: (id: string, type: EntityType) => void;
  clearSelection: () => void;
}

export const useInspect = create<InspectState>((set) => ({
  selectedEntityId: null,
  selectedEntityType: null,

  selectEntity: (id, type) =>
    set({ selectedEntityId: id, selectedEntityType: type }),

  clearSelection: () =>
    set({ selectedEntityId: null, selectedEntityType: null }),
}));
