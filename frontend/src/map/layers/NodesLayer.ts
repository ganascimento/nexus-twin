import { ScatterplotLayer } from "@deck.gl/layers";
import type {
  FactorySnapshot,
  WarehouseSnapshot,
  StoreSnapshot,
  EntityType,
} from "../../types/world";
import {
  FACTORY_COLOR,
  WAREHOUSE_COLOR,
  STORE_COLOR,
  ALERT_COLOR,
} from "../mapConfig";

interface NodeDatum {
  id: string;
  entityType: EntityType;
  position: [number, number];
  totalStock: number;
  isAlert: boolean;
  color: [number, number, number];
}

function mapFactories(factories: FactorySnapshot[]): NodeDatum[] {
  return factories.map((f) => {
    const totalStock = f.products.reduce((sum, p) => sum + p.stock, 0);
    return {
      id: f.id,
      entityType: "factory" as const,
      position: [f.lng, f.lat],
      totalStock,
      isAlert: f.status !== "operating",
      color: FACTORY_COLOR,
    };
  });
}

function mapWarehouses(warehouses: WarehouseSnapshot[]): NodeDatum[] {
  return warehouses.map((w) => {
    const totalStock = w.stocks.reduce((sum, s) => sum + s.stock, 0);
    const totalMinStock = w.stocks.reduce((sum, s) => sum + s.min_stock, 0);
    return {
      id: w.id,
      entityType: "warehouse" as const,
      position: [w.lng, w.lat],
      totalStock,
      isAlert: w.status !== "operating" || totalStock < totalMinStock,
      color: WAREHOUSE_COLOR,
    };
  });
}

function mapStores(stores: StoreSnapshot[]): NodeDatum[] {
  return stores.map((s) => {
    const totalStock = s.stocks.reduce((sum, st) => sum + st.stock, 0);
    const totalReorder = s.stocks.reduce((sum, st) => sum + st.reorder_point, 0);
    return {
      id: s.id,
      entityType: "store" as const,
      position: [s.lng, s.lat],
      totalStock,
      isAlert: s.status !== "open" || totalStock < totalReorder,
      color: STORE_COLOR,
    };
  });
}

export function createNodesLayer(
  factories: FactorySnapshot[],
  warehouses: WarehouseSnapshot[],
  stores: StoreSnapshot[],
): ScatterplotLayer<NodeDatum> {
  const data = [
    ...mapFactories(factories),
    ...mapWarehouses(warehouses),
    ...mapStores(stores),
  ];

  return new ScatterplotLayer<NodeDatum>({
    id: "nodes-layer",
    data,
    getPosition: (d) => d.position,
    getRadius: (d) =>
      d.entityType === "factory" ? 2000 : d.entityType === "warehouse" ? 1500 : 1200,
    getFillColor: (d) => (d.isAlert ? ALERT_COLOR : d.color),
    radiusUnits: "meters",
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
  });
}
