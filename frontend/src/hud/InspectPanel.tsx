import { useInspect } from "@/hooks/useInspect";
import { useWorldStore } from "@/store/worldStore";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type {
  FactorySnapshot,
  WarehouseSnapshot,
  StoreSnapshot,
  TruckSnapshot,
  EntityType,
} from "@/types/world";

const ENTITY_ICONS: Record<EntityType, string> = {
  factory: "🏭",
  warehouse: "📦",
  store: "🏪",
  truck: "🚚",
};

const ENTITY_LABELS: Record<EntityType, string> = {
  factory: "Fábrica",
  warehouse: "Armazém",
  store: "Loja",
  truck: "Caminhão",
};

const ACTION_LABELS: Record<string, string> = {
  order_replenishment: "pediu reposição",
  confirm_order: "confirmou pedido",
  reject_order: "rejeitou pedido",
  request_resupply: "pediu reabastecimento",
  start_production: "iniciou produção",
  stop_production: "parou produção",
  send_stock: "enviou estoque",
  accept_contract: "aceitou contrato",
  refuse_contract: "recusou contrato",
  request_maintenance: "solicitou manutenção",
  alert_breakdown: "avisou quebra",
  reroute: "remarcou rota",
  hold: "hold",
};

const FACTORY_STATUS_COLORS: Record<string, string> = {
  operating: "bg-green-600",
  reduced_capacity: "bg-yellow-600",
  stopped: "bg-red-600",
};

const WAREHOUSE_STATUS_COLORS: Record<string, string> = {
  operating: "bg-green-600",
  rationing: "bg-yellow-600",
  offline: "bg-red-600",
};

const STORE_STATUS_COLORS: Record<string, string> = {
  open: "bg-green-600",
  demand_paused: "bg-yellow-600",
  offline: "bg-red-600",
};

const TRUCK_STATUS_COLORS: Record<string, string> = {
  idle: "bg-gray-500",
  evaluating: "bg-yellow-600",
  in_transit: "bg-green-600",
  broken: "bg-red-600",
  maintenance: "bg-orange-500",
};

const DECISIONS_LIMIT = 10;

function degradationColor(value: number): string {
  if (value < 40) return "#22c55e";
  if (value < 70) return "#eab308";
  return "#ef4444";
}

function StatusBadge({ status, colorMap }: { status: string; colorMap: Record<string, string> }) {
  return (
    <Badge className={colorMap[status] ?? "bg-gray-500"}>
      {status}
    </Badge>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mt-4 mb-2">
      {children}
    </h3>
  );
}

function DataTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/10">
            {headers.map((h) => (
              <th key={h} className="text-left py-1 px-1 text-white/50 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function FactoryDetails({ factory }: { factory: FactorySnapshot }) {
  return (
    <div>
      <div className="mb-3">
        <StatusBadge status={factory.status} colorMap={FACTORY_STATUS_COLORS} />
      </div>

      <SectionHeader>Products</SectionHeader>
      <DataTable headers={["Material", "Stock", "Rsvd", "Max", "Rate", "Max Rate"]}>
        {factory.products.map((p) => (
          <tr key={p.material_id} className="border-b border-white/5">
            <td className="py-1 px-1 font-mono">{p.material_id}</td>
            <td className="py-1 px-1">{p.stock}</td>
            <td className="py-1 px-1">{p.stock_reserved}</td>
            <td className="py-1 px-1">{p.stock_max}</td>
            <td className="py-1 px-1">{p.production_rate_current}</td>
            <td className="py-1 px-1">{p.production_rate_max}</td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}

function WarehouseDetails({ warehouse }: { warehouse: WarehouseSnapshot }) {
  return (
    <div>
      <div className="mb-2">
        <StatusBadge status={warehouse.status} colorMap={WAREHOUSE_STATUS_COLORS} />
      </div>
      <div className="text-xs text-white/60 mb-3 space-y-0.5">
        <p>Região: {warehouse.region}</p>
        <p>Capacidade: {warehouse.capacity_total} t</p>
      </div>

      <SectionHeader>Stocks</SectionHeader>
      <DataTable headers={["Material", "Stock", "Rsvd", "Min Stock"]}>
        {warehouse.stocks.map((s) => (
          <tr key={s.material_id} className="border-b border-white/5">
            <td className="py-1 px-1 font-mono">{s.material_id}</td>
            <td className="py-1 px-1">{s.stock}</td>
            <td className="py-1 px-1">{s.stock_reserved}</td>
            <td className="py-1 px-1">{s.min_stock}</td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}

function StoreDetails({ store }: { store: StoreSnapshot }) {
  return (
    <div>
      <div className="mb-3">
        <StatusBadge status={store.status} colorMap={STORE_STATUS_COLORS} />
      </div>

      <SectionHeader>Stocks</SectionHeader>
      <DataTable headers={["Material", "Stock", "Demand/tick", "Reorder Pt"]}>
        {store.stocks.map((s) => (
          <tr key={s.material_id} className="border-b border-white/5">
            <td className="py-1 px-1 font-mono">{s.material_id}</td>
            <td className="py-1 px-1">{s.stock}</td>
            <td className="py-1 px-1">{s.demand_rate}</td>
            <td className="py-1 px-1">{s.reorder_point}</td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}

function DegradationBar({ value }: { value: number }) {
  return (
    <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
      <div
        className="h-full rounded-full transition-all"
        style={{
          width: `${Math.min(value, 100)}%`,
          backgroundColor: degradationColor(value),
        }}
      />
    </div>
  );
}

function TruckDetails({ truck }: { truck: TruckSnapshot }) {
  const truckTypeBg = truck.truck_type === "proprietario" ? "bg-blue-600" : "bg-cyan-600";

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Badge className={truckTypeBg}>{truck.truck_type}</Badge>
        <StatusBadge status={truck.status} colorMap={TRUCK_STATUS_COLORS} />
      </div>

      <div className="space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-white/60">Capacity</span>
          <span>{truck.capacity_tons} tons</span>
        </div>

        <div>
          <div className="flex justify-between mb-1">
            <span className="text-white/60">Degradation</span>
            <span>{truck.degradation.toFixed(1)}%</span>
          </div>
          <DegradationBar value={truck.degradation} />
        </div>

        <div className="flex justify-between">
          <span className="text-white/60">Breakdown Risk</span>
          <span>{truck.breakdown_risk.toFixed(1)}%</span>
        </div>

        {truck.truck_type === "proprietario" && truck.factory_id && (
          <div className="flex justify-between">
            <span className="text-white/60">Factory</span>
            <span className="font-mono">{truck.factory_id}</span>
          </div>
        )}
      </div>

      {truck.cargo && (
        <>
          <SectionHeader>Cargo</SectionHeader>
          <div className="text-xs space-y-1 bg-white/5 rounded p-2">
            <div className="flex justify-between">
              <span className="text-white/60">Product</span>
              <span>{truck.cargo.product}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Quantity</span>
              <span>{truck.cargo.quantity} tons</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Origin</span>
              <span className="font-mono truncate ml-2">{truck.cargo.origin}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Destination</span>
              <span className="font-mono truncate ml-2">{truck.cargo.destination}</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function useSelectedEntity(): {
  entity: FactorySnapshot | WarehouseSnapshot | StoreSnapshot | TruckSnapshot | null;
  entityType: EntityType | null;
} {
  const selectedEntityId = useInspect((s) => s.selectedEntityId);
  const selectedEntityType = useInspect((s) => s.selectedEntityType);
  const factories = useWorldStore((s) => s.factories);
  const warehouses = useWorldStore((s) => s.warehouses);
  const stores = useWorldStore((s) => s.stores);
  const trucks = useWorldStore((s) => s.trucks);

  if (!selectedEntityId || !selectedEntityType) {
    return { entity: null, entityType: null };
  }

  switch (selectedEntityType) {
    case "factory":
      return { entity: factories.find((f) => f.id === selectedEntityId) ?? null, entityType: selectedEntityType };
    case "warehouse":
      return { entity: warehouses.find((w) => w.id === selectedEntityId) ?? null, entityType: selectedEntityType };
    case "store":
      return { entity: stores.find((s) => s.id === selectedEntityId) ?? null, entityType: selectedEntityType };
    case "truck":
      return { entity: trucks.find((t) => t.id === selectedEntityId) ?? null, entityType: selectedEntityType };
    default:
      return { entity: null, entityType: null };
  }
}

function EntityView({ entity, entityType }: {
  entity: FactorySnapshot | WarehouseSnapshot | StoreSnapshot | TruckSnapshot;
  entityType: EntityType;
}) {
  switch (entityType) {
    case "factory":
      return <FactoryDetails factory={entity as FactorySnapshot} />;
    case "warehouse":
      return <WarehouseDetails warehouse={entity as WarehouseSnapshot} />;
    case "store":
      return <StoreDetails store={entity as StoreSnapshot} />;
    case "truck":
      return <TruckDetails truck={entity as TruckSnapshot} />;
    default:
      return null;
  }
}

export default function InspectPanel() {
  const selectedEntityId = useInspect((s) => s.selectedEntityId);
  const clearSelection = useInspect((s) => s.clearSelection);
  const recentDecisions = useWorldStore((s) => s.recentDecisions);
  const { entity, entityType } = useSelectedEntity();

  if (!selectedEntityId) {
    return null;
  }

  const entityDecisions = recentDecisions
    .filter((d) => d.entity_id === selectedEntityId)
    .slice(0, DECISIONS_LIMIT);

  const entityName = entity && "name" in entity ? entity.name : null;
  const entityIcon = entityType ? ENTITY_ICONS[entityType] : "❓";
  const entityLabel = entityType ? ENTITY_LABELS[entityType] : "Entidade";

  return (
    <div className="fixed top-12 right-0 bottom-0 z-40 w-80 bg-black/80 backdrop-blur text-white pointer-events-auto border-l border-t border-white/10">
      <ScrollArea className="h-full">
        <div className="p-4">
          <div className="flex items-start gap-3 mb-4">
            <span className="text-3xl leading-none" aria-hidden="true">
              {entityIcon}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-white/40 font-semibold">
                {entityLabel}
              </div>
              <div className="text-sm font-bold truncate">
                {entityName ?? selectedEntityId}
              </div>
              <div className="text-[10px] font-mono text-white/50 truncate">
                {selectedEntityId}
              </div>
            </div>
            <button
              type="button"
              onClick={clearSelection}
              className="text-white/50 hover:text-white transition-colors p-1 rounded hover:bg-white/10 shrink-0"
              aria-label="Close inspector"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="1" y1="1" x2="13" y2="13" />
                <line x1="13" y1="1" x2="1" y2="13" />
              </svg>
            </button>
          </div>

          {!entity ? (
            <p className="text-sm text-white/40">Entity not found</p>
          ) : (
            <EntityView entity={entity} entityType={entityType!} />
          )}

          <div className="border-t border-white/10 mt-4 pt-2">
            <SectionHeader>Recent Decisions</SectionHeader>
            {entityDecisions.length === 0 ? (
              <p className="text-xs text-white/30">No decisions yet</p>
            ) : (
              <div className="space-y-1.5">
                {entityDecisions.map((d, i) => (
                  <div
                    key={`${d.tick}-${d.action}-${i}`}
                    className="bg-white/5 rounded p-2 text-xs"
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-semibold text-white/80">
                        {ACTION_LABELS[d.action] ?? d.action}
                      </span>
                      <span className="text-[10px] text-white/40">T{d.tick}</span>
                    </div>
                    {d.summary && (
                      <p className="text-white/60 line-clamp-2">{d.summary}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
