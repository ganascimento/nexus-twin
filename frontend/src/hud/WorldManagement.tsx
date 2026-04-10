import { useState, useEffect, useCallback } from "react";
import { useWorldStore } from "@/store/worldStore";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import {
  listMaterials,
  createMaterial,
  updateMaterial,
  deactivateMaterial,
  createFactory,
  deleteFactory,
  createWarehouse,
  deleteWarehouse,
  createStore,
  deleteStore,
  createTruck,
  deleteTruck,
  adjustStock,
  type MaterialResponse,
} from "@/lib/api";

type TabId =
  | "materials"
  | "factories"
  | "warehouses"
  | "stores"
  | "trucks"
  | "stock";

const TABS: { id: TabId; label: string }[] = [
  { id: "materials", label: "Materials" },
  { id: "factories", label: "Factories" },
  { id: "warehouses", label: "Warehouses" },
  { id: "stores", label: "Stores" },
  { id: "trucks", label: "Trucks" },
  { id: "stock", label: "Stock" },
];

export default function WorldManagement() {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("materials");

  return (
    <div className="fixed top-16 left-4 z-40" style={{ pointerEvents: "auto" }}>
      <Button
        onClick={() => setOpen(true)}
        className="bg-gray-800 hover:bg-gray-700 text-white border border-gray-600 shadow-lg"
        size="sm"
      >
        Manage World
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col bg-gray-900 text-white border-gray-700 p-0">
          <DialogHeader className="px-6 pt-6 pb-0">
            <DialogTitle className="text-white">World Management</DialogTitle>
            <DialogDescription className="text-gray-400">
              Create, manage, and configure world entities and materials.
            </DialogDescription>
          </DialogHeader>

          <div className="flex gap-1 px-6 pt-2 pb-0 border-b border-gray-700 overflow-x-auto">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-2 text-sm font-medium rounded-t transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? "bg-gray-700 text-white border-b-2 border-blue-500"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-hidden px-6 pb-6">
            <ScrollArea className="h-full max-h-[calc(85vh-160px)]">
              <div className="pr-4">
                {activeTab === "materials" && <MaterialsTab />}
                {activeTab === "factories" && <FactoriesTab />}
                {activeTab === "warehouses" && <WarehousesTab />}
                {activeTab === "stores" && <StoresTab />}
                {activeTab === "trucks" && <TrucksTab />}
                {activeTab === "stock" && <StockTab />}
              </div>
            </ScrollArea>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Materials Tab
// ---------------------------------------------------------------------------

function MaterialsTab() {
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const loadMaterials = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMaterials();
      setMaterials(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load materials");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMaterials();
  }, [loadMaterials]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setError(null);
    try {
      await createMaterial({ name: newName.trim() });
      setNewName("");
      await loadMaterials();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create material");
    }
  };

  const handleUpdate = async (id: string) => {
    if (!editingName.trim()) return;
    setError(null);
    try {
      await updateMaterial(id, { name: editingName.trim() });
      setEditingId(null);
      setEditingName("");
      await loadMaterials();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update material");
    }
  };

  const handleDeactivate = async (id: string) => {
    setError(null);
    try {
      await deactivateMaterial(id);
      await loadMaterials();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to deactivate material"
      );
    }
  };

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <Input
          placeholder="New material name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500 flex-1"
        />
        <Button onClick={handleCreate} size="sm" className="bg-blue-600 hover:bg-blue-700">
          Create
        </Button>
      </div>

      {loading ? (
        <p className="text-gray-400 text-sm">Loading...</p>
      ) : (
        <div className="border border-gray-700 rounded overflow-hidden">
          <div className="grid grid-cols-[1fr_2fr_80px_120px] gap-2 px-3 py-2 bg-gray-800 text-xs font-semibold text-gray-400 uppercase">
            <span>ID</span>
            <span>Name</span>
            <span>Active</span>
            <span>Actions</span>
          </div>
          {materials.length === 0 && (
            <div className="px-3 py-4 text-gray-500 text-sm text-center">
              No materials found.
            </div>
          )}
          {materials.map((m) => (
            <div
              key={m.id}
              className="grid grid-cols-[1fr_2fr_80px_120px] gap-2 px-3 py-2 border-t border-gray-700 items-center text-sm"
            >
              <span className="text-gray-400 font-mono text-xs truncate">
                {m.id}
              </span>

              {editingId === m.id ? (
                <div className="flex gap-1">
                  <Input
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleUpdate(m.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    className="bg-gray-800 border-gray-600 text-white h-7 text-sm"
                    autoFocus
                  />
                  <Button
                    onClick={() => handleUpdate(m.id)}
                    size="xs"
                    className="bg-green-600 hover:bg-green-700"
                  >
                    Save
                  </Button>
                </div>
              ) : (
                <span>{m.name}</span>
              )}

              <Badge className={m.is_active ? "bg-green-700" : "bg-red-700"}>
                {m.is_active ? "Active" : "Inactive"}
              </Badge>

              <div className="flex gap-1">
                {editingId !== m.id && (
                  <Button
                    onClick={() => {
                      setEditingId(m.id);
                      setEditingName(m.name);
                    }}
                    size="xs"
                    variant="ghost"
                    className="text-blue-400 hover:text-blue-300 hover:bg-gray-700"
                  >
                    Edit
                  </Button>
                )}
                {m.is_active && (
                  <Button
                    onClick={() => handleDeactivate(m.id)}
                    size="xs"
                    variant="ghost"
                    className="text-red-400 hover:text-red-300 hover:bg-gray-700"
                  >
                    Deactivate
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Factories Tab
// ---------------------------------------------------------------------------

function FactoriesTab() {
  const factories = useWorldStore((s) => s.factories);
  const [error, setError] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formLat, setFormLat] = useState("");
  const [formLng, setFormLng] = useState("");

  const handleCreate = async () => {
    if (!formName.trim() || !formLat || !formLng) return;
    setError(null);
    try {
      await createFactory({
        name: formName.trim(),
        lat: parseFloat(formLat),
        lng: parseFloat(formLng),
      });
      setFormName("");
      setFormLat("");
      setFormLng("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create factory");
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete factory "${name}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deleteFactory(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete factory");
    }
  };

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-300">Create Factory</h3>
        <div className="flex gap-2 flex-wrap">
          <div className="flex-1 min-w-[150px]">
            <Label className="text-gray-400 text-xs">Name</Label>
            <Input
              placeholder="Factory name"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Latitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-23.55"
              value={formLat}
              onChange={(e) => setFormLat(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Longitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-46.63"
              value={formLng}
              onChange={(e) => setFormLng(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="flex items-end">
            <Button onClick={handleCreate} size="sm" className="bg-blue-600 hover:bg-blue-700">
              Create
            </Button>
          </div>
        </div>
      </div>

      <div className="border border-gray-700 rounded overflow-hidden">
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_80px] gap-2 px-3 py-2 bg-gray-800 text-xs font-semibold text-gray-400 uppercase">
          <span>Name</span>
          <span>Status</span>
          <span>Lat</span>
          <span>Lng</span>
          <span>Actions</span>
        </div>
        {factories.length === 0 && (
          <div className="px-3 py-4 text-gray-500 text-sm text-center">
            No factories found.
          </div>
        )}
        {factories.map((f) => (
          <div
            key={f.id}
            className="grid grid-cols-[2fr_1fr_1fr_1fr_80px] gap-2 px-3 py-2 border-t border-gray-700 items-center text-sm"
          >
            <span className="truncate">{f.name}</span>
            <StatusBadge status={f.status} />
            <span className="text-gray-400 text-xs">{f.lat.toFixed(4)}</span>
            <span className="text-gray-400 text-xs">{f.lng.toFixed(4)}</span>
            <Button
              onClick={() => handleDelete(f.id, f.name)}
              size="xs"
              variant="ghost"
              className="text-red-400 hover:text-red-300 hover:bg-gray-700"
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Warehouses Tab
// ---------------------------------------------------------------------------

function WarehousesTab() {
  const warehouses = useWorldStore((s) => s.warehouses);
  const [error, setError] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formLat, setFormLat] = useState("");
  const [formLng, setFormLng] = useState("");
  const [formRegion, setFormRegion] = useState("");
  const [formCapacity, setFormCapacity] = useState("");

  const handleCreate = async () => {
    if (!formName.trim() || !formLat || !formLng || !formRegion.trim() || !formCapacity)
      return;
    setError(null);
    try {
      await createWarehouse({
        name: formName.trim(),
        lat: parseFloat(formLat),
        lng: parseFloat(formLng),
        region: formRegion.trim(),
        capacity_total: parseFloat(formCapacity),
      });
      setFormName("");
      setFormLat("");
      setFormLng("");
      setFormRegion("");
      setFormCapacity("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create warehouse"
      );
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete warehouse "${name}"? This cannot be undone.`))
      return;
    setError(null);
    try {
      await deleteWarehouse(id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete warehouse"
      );
    }
  };

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-300">
          Create Warehouse
        </h3>
        <div className="flex gap-2 flex-wrap">
          <div className="flex-1 min-w-[140px]">
            <Label className="text-gray-400 text-xs">Name</Label>
            <Input
              placeholder="Warehouse name"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Latitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-23.55"
              value={formLat}
              onChange={(e) => setFormLat(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Longitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-46.63"
              value={formLng}
              onChange={(e) => setFormLng(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Region</Label>
            <Input
              placeholder="Region"
              value={formRegion}
              onChange={(e) => setFormRegion(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Capacity</Label>
            <Input
              type="number"
              step="any"
              placeholder="1000"
              value={formCapacity}
              onChange={(e) => setFormCapacity(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleCreate}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700"
            >
              Create
            </Button>
          </div>
        </div>
      </div>

      <div className="border border-gray-700 rounded overflow-hidden">
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_80px] gap-2 px-3 py-2 bg-gray-800 text-xs font-semibold text-gray-400 uppercase">
          <span>Name</span>
          <span>Region</span>
          <span>Capacity</span>
          <span>Status</span>
          <span>Actions</span>
        </div>
        {warehouses.length === 0 && (
          <div className="px-3 py-4 text-gray-500 text-sm text-center">
            No warehouses found.
          </div>
        )}
        {warehouses.map((w) => (
          <div
            key={w.id}
            className="grid grid-cols-[2fr_1fr_1fr_1fr_80px] gap-2 px-3 py-2 border-t border-gray-700 items-center text-sm"
          >
            <span className="truncate">{w.name}</span>
            <span className="text-gray-400 text-xs">{w.region}</span>
            <span className="text-gray-400 text-xs">{w.capacity_total}</span>
            <StatusBadge status={w.status} />
            <Button
              onClick={() => handleDelete(w.id, w.name)}
              size="xs"
              variant="ghost"
              className="text-red-400 hover:text-red-300 hover:bg-gray-700"
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stores Tab
// ---------------------------------------------------------------------------

function StoresTab() {
  const stores = useWorldStore((s) => s.stores);
  const [error, setError] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formLat, setFormLat] = useState("");
  const [formLng, setFormLng] = useState("");
  const [formRegion, setFormRegion] = useState("");

  const handleCreate = async () => {
    if (!formName.trim() || !formLat || !formLng || !formRegion.trim()) return;
    setError(null);
    try {
      await createStore({
        name: formName.trim(),
        lat: parseFloat(formLat),
        lng: parseFloat(formLng),
        region: formRegion.trim(),
      });
      setFormName("");
      setFormLat("");
      setFormLng("");
      setFormRegion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create store");
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete store "${name}"? This cannot be undone.`))
      return;
    setError(null);
    try {
      await deleteStore(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete store");
    }
  };

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-300">Create Store</h3>
        <div className="flex gap-2 flex-wrap">
          <div className="flex-1 min-w-[150px]">
            <Label className="text-gray-400 text-xs">Name</Label>
            <Input
              placeholder="Store name"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Latitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-23.55"
              value={formLat}
              onChange={(e) => setFormLat(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Longitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-46.63"
              value={formLng}
              onChange={(e) => setFormLng(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Region</Label>
            <Input
              placeholder="Region"
              value={formRegion}
              onChange={(e) => setFormRegion(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleCreate}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700"
            >
              Create
            </Button>
          </div>
        </div>
      </div>

      <div className="border border-gray-700 rounded overflow-hidden">
        <div className="grid grid-cols-[2fr_1fr_1fr_80px] gap-2 px-3 py-2 bg-gray-800 text-xs font-semibold text-gray-400 uppercase">
          <span>Name</span>
          <span>Status</span>
          <span>Location</span>
          <span>Actions</span>
        </div>
        {stores.length === 0 && (
          <div className="px-3 py-4 text-gray-500 text-sm text-center">
            No stores found.
          </div>
        )}
        {stores.map((s) => (
          <div
            key={s.id}
            className="grid grid-cols-[2fr_1fr_1fr_80px] gap-2 px-3 py-2 border-t border-gray-700 items-center text-sm"
          >
            <span className="truncate">{s.name}</span>
            <StatusBadge status={s.status} />
            <span className="text-gray-400 text-xs">
              {s.lat.toFixed(4)}, {s.lng.toFixed(4)}
            </span>
            <Button
              onClick={() => handleDelete(s.id, s.name)}
              size="xs"
              variant="ghost"
              className="text-red-400 hover:text-red-300 hover:bg-gray-700"
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trucks Tab
// ---------------------------------------------------------------------------

function TrucksTab() {
  const trucks = useWorldStore((s) => s.trucks);
  const [error, setError] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState<string>("proprietario");
  const [formLat, setFormLat] = useState("");
  const [formLng, setFormLng] = useState("");

  const handleCreate = async () => {
    if (!formName.trim() || !formLat || !formLng) return;
    setError(null);
    try {
      await createTruck({
        name: formName.trim(),
        truck_type: formType,
        lat: parseFloat(formLat),
        lng: parseFloat(formLng),
      });
      setFormName("");
      setFormLat("");
      setFormLng("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create truck");
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(`Delete truck "${id}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deleteTruck(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete truck");
    }
  };

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-300">Create Truck</h3>
        <div className="flex gap-2 flex-wrap">
          <div className="flex-1 min-w-[140px]">
            <Label className="text-gray-400 text-xs">Name</Label>
            <Input
              placeholder="Truck name"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-40">
            <Label className="text-gray-400 text-xs">Type</Label>
            <Select value={formType} onValueChange={setFormType}>
              <SelectTrigger className="bg-gray-800 border-gray-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-gray-800 border-gray-600 text-white">
                <SelectItem value="proprietario">Proprietario</SelectItem>
                <SelectItem value="terceiro">Terceiro</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Latitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-23.55"
              value={formLat}
              onChange={(e) => setFormLat(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="w-28">
            <Label className="text-gray-400 text-xs">Longitude</Label>
            <Input
              type="number"
              step="any"
              placeholder="-46.63"
              value={formLng}
              onChange={(e) => setFormLng(e.target.value)}
              className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleCreate}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700"
            >
              Create
            </Button>
          </div>
        </div>
      </div>

      <div className="border border-gray-700 rounded overflow-hidden">
        <div className="grid grid-cols-[1fr_1fr_80px_100px_1fr_80px] gap-2 px-3 py-2 bg-gray-800 text-xs font-semibold text-gray-400 uppercase">
          <span>ID</span>
          <span>Type</span>
          <span>Capacity</span>
          <span>Degradation</span>
          <span>Status</span>
          <span>Actions</span>
        </div>
        {trucks.length === 0 && (
          <div className="px-3 py-4 text-gray-500 text-sm text-center">
            No trucks found.
          </div>
        )}
        {trucks.map((t) => (
          <div
            key={t.id}
            className="grid grid-cols-[1fr_1fr_80px_100px_1fr_80px] gap-2 px-3 py-2 border-t border-gray-700 items-center text-sm"
          >
            <span className="text-gray-400 font-mono text-xs truncate">
              {t.id}
            </span>
            <Badge
              className={
                t.truck_type === "proprietario" ? "bg-blue-700" : "bg-amber-700"
              }
            >
              {t.truck_type}
            </Badge>
            <span className="text-gray-400 text-xs">{t.capacity_tons}t</span>
            <DegradationBar value={t.degradation} />
            <StatusBadge status={t.status} />
            <Button
              onClick={() => handleDelete(t.id)}
              size="xs"
              variant="ghost"
              className="text-red-400 hover:text-red-300 hover:bg-gray-700"
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stock Tab
// ---------------------------------------------------------------------------

function StockTab() {
  const factories = useWorldStore((s) => s.factories);
  const warehouses = useWorldStore((s) => s.warehouses);
  const stores = useWorldStore((s) => s.stores);

  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [entityType, setEntityType] = useState<string>("");
  const [entityId, setEntityId] = useState<string>("");
  const [materialId, setMaterialId] = useState<string>("");
  const [delta, setDelta] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    listMaterials(true)
      .then(setMaterials)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setEntityId("");
  }, [entityType]);

  const entitiesForType = () => {
    if (entityType === "factories")
      return factories.map((f) => ({ id: f.id, label: f.name }));
    if (entityType === "warehouses")
      return warehouses.map((w) => ({ id: w.id, label: w.name }));
    if (entityType === "stores")
      return stores.map((s) => ({ id: s.id, label: s.name }));
    return [];
  };

  const handleAdjust = async () => {
    if (!entityType || !entityId || !materialId || !delta) return;
    setError(null);
    setSuccess(null);
    try {
      await adjustStock(entityType, entityId, {
        material_id: materialId,
        delta: parseFloat(delta),
      });
      setSuccess("Stock adjusted successfully.");
      setDelta("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to adjust stock");
    }
  };

  const entities = entitiesForType();

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-900/50 border border-green-700 text-green-200 px-3 py-2 rounded text-sm">
          {success}
        </div>
      )}

      <div className="space-y-3 max-w-md">
        <div>
          <Label className="text-gray-400 text-xs">Entity Type</Label>
          <Select value={entityType} onValueChange={setEntityType}>
            <SelectTrigger className="bg-gray-800 border-gray-600 text-white">
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent className="bg-gray-800 border-gray-600 text-white">
              <SelectItem value="factories">Factory</SelectItem>
              <SelectItem value="warehouses">Warehouse</SelectItem>
              <SelectItem value="stores">Store</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="text-gray-400 text-xs">Entity</Label>
          <Select
            value={entityId}
            onValueChange={setEntityId}
            disabled={entities.length === 0}
          >
            <SelectTrigger className="bg-gray-800 border-gray-600 text-white">
              <SelectValue placeholder="Select entity" />
            </SelectTrigger>
            <SelectContent className="bg-gray-800 border-gray-600 text-white">
              {entities.map((e) => (
                <SelectItem key={e.id} value={e.id}>
                  {e.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="text-gray-400 text-xs">Material</Label>
          <Select
            value={materialId}
            onValueChange={setMaterialId}
            disabled={materials.length === 0}
          >
            <SelectTrigger className="bg-gray-800 border-gray-600 text-white">
              <SelectValue placeholder="Select material" />
            </SelectTrigger>
            <SelectContent className="bg-gray-800 border-gray-600 text-white">
              {materials.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="text-gray-400 text-xs">
            Delta (positive to add, negative to remove)
          </Label>
          <Input
            type="number"
            step="any"
            placeholder="10 or -5"
            value={delta}
            onChange={(e) => setDelta(e.target.value)}
            className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-500"
          />
        </div>

        <Button
          onClick={handleAdjust}
          className="bg-blue-600 hover:bg-blue-700 w-full"
          disabled={!entityType || !entityId || !materialId || !delta}
        >
          Adjust Stock
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared utility components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    operating: "bg-green-700",
    open: "bg-green-700",
    idle: "bg-gray-600",
    stopped: "bg-red-700",
    offline: "bg-red-700",
    broken: "bg-red-700",
    reduced_capacity: "bg-yellow-700",
    rationing: "bg-yellow-700",
    demand_paused: "bg-yellow-700",
    in_transit: "bg-blue-700",
    evaluating: "bg-purple-700",
    maintenance: "bg-orange-700",
  };

  return (
    <Badge className={colorMap[status] ?? "bg-gray-600"}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

function DegradationBar({ value }: { value: number }) {
  const percentage = Math.min(Math.max(value * 100, 0), 100);
  const barColor =
    percentage < 40
      ? "bg-green-500"
      : percentage < 70
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <div className="flex items-center gap-1">
      <div className="w-16 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-gray-400 text-xs">{percentage.toFixed(0)}%</span>
    </div>
  );
}
