import { useState } from "react";
import { useWorldStore } from "@/store/worldStore";
import { injectChaosEvent, resolveChaosEvent } from "@/lib/api";
import type { ChaosEventCreate } from "@/lib/api";
import type { ChaosEventSource } from "@/types/world";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";

const EVENT_TYPES = [
  "route_blocked",
  "machine_breakdown",
  "demand_spike",
  "regional_storm",
  "trucker_strike",
  "truck_breakdown",
  "demand_zero",
] as const;

type EventType = (typeof EVENT_TYPES)[number];

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  route_blocked: "Route Blocked",
  machine_breakdown: "Machine Breakdown",
  demand_spike: "Demand Spike",
  regional_storm: "Regional Storm",
  trucker_strike: "Trucker Strike",
  truck_breakdown: "Truck Breakdown",
  demand_zero: "Demand Zero",
};

const SOURCE_BADGE_STYLES: Record<ChaosEventSource, { label: string; className: string }> = {
  user: { label: "User", className: "bg-blue-600 text-white hover:bg-blue-600" },
  master_agent: { label: "MasterAgent", className: "bg-purple-600 text-white hover:bg-purple-600" },
  engine: { label: "Engine", className: "bg-gray-600 text-white hover:bg-gray-600" },
};

function InjectEventForm() {
  const tick = useWorldStore((s) => s.tick);
  const factories = useWorldStore((s) => s.factories);
  const stores = useWorldStore((s) => s.stores);
  const trucks = useWorldStore((s) => s.trucks);

  const [eventType, setEventType] = useState<EventType | "">("");
  const [entityId, setEntityId] = useState("");
  const [highway, setHighway] = useState("");
  const [region, setRegion] = useState("");
  const [durationTicks, setDurationTicks] = useState(6);
  const [multiplier, setMultiplier] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function resetFields() {
    setEntityId("");
    setHighway("");
    setRegion("");
    setDurationTicks(6);
    setMultiplier(3);
    setError("");
  }

  function handleEventTypeChange(value: string) {
    setEventType(value as EventType);
    resetFields();
  }

  function buildPayload(): ChaosEventCreate | null {
    if (!eventType) return null;

    switch (eventType) {
      case "route_blocked":
        return {
          event_type: eventType,
          entity_type: "",
          entity_id: "",
          payload: { highway, duration_ticks: durationTicks },
        };
      case "machine_breakdown":
        if (!entityId) return null;
        return {
          event_type: eventType,
          entity_type: "factory",
          entity_id: entityId,
          payload: { duration_ticks: durationTicks },
        };
      case "demand_spike":
        if (!entityId) return null;
        return {
          event_type: eventType,
          entity_type: "store",
          entity_id: entityId,
          payload: { multiplier, duration_ticks: durationTicks },
        };
      case "regional_storm":
        return {
          event_type: eventType,
          entity_type: "",
          entity_id: "",
          payload: { region, duration_ticks: durationTicks },
        };
      case "trucker_strike":
        return {
          event_type: eventType,
          entity_type: "",
          entity_id: "",
          payload: { duration_ticks: durationTicks },
        };
      case "truck_breakdown":
        if (!entityId) return null;
        return {
          event_type: eventType,
          entity_type: "truck",
          entity_id: entityId,
        };
      case "demand_zero":
        if (!entityId) return null;
        return {
          event_type: eventType,
          entity_type: "store",
          entity_id: entityId,
          payload: { duration_ticks: durationTicks },
        };
      default:
        return null;
    }
  }

  async function handleInject() {
    const payload = buildPayload();
    if (!payload) return;

    setSubmitting(true);
    setError("");
    try {
      await injectChaosEvent(payload, tick);
      setEventType("");
      resetFields();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to inject event";
      setError(message);
      console.error("Failed to inject chaos event:", err);
    } finally {
      setSubmitting(false);
    }
  }

  const needsEntitySelect = eventType === "machine_breakdown"
    || eventType === "demand_spike"
    || eventType === "truck_breakdown"
    || eventType === "demand_zero";

  const entityOptions = (() => {
    switch (eventType) {
      case "machine_breakdown":
        return factories.map((f) => ({ value: f.id, label: f.name }));
      case "demand_spike":
      case "demand_zero":
        return stores.map((s) => ({ value: s.id, label: s.name }));
      case "truck_breakdown":
        return trucks.map((t) => ({ value: t.id, label: t.id }));
      default:
        return [];
    }
  })();

  const needsDurationTicks = eventType !== "" && eventType !== "truck_breakdown";
  const needsHighway = eventType === "route_blocked";
  const needsRegion = eventType === "regional_storm";
  const needsMultiplier = eventType === "demand_spike";

  const canSubmit = (() => {
    if (!eventType || submitting) return false;
    if (needsEntitySelect && !entityId) return false;
    if (needsHighway && !highway.trim()) return false;
    if (needsRegion && !region.trim()) return false;
    return true;
  })();

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
        Inject Event
      </p>

      <Select value={eventType} onValueChange={handleEventTypeChange}>
        <SelectTrigger className="h-8 bg-zinc-900 border-zinc-700 text-white text-xs">
          <SelectValue placeholder="Select event type..." />
        </SelectTrigger>
        <SelectContent className="bg-zinc-900 border-zinc-700">
          {EVENT_TYPES.map((type) => (
            <SelectItem key={type} value={type} className="text-white text-xs hover:bg-zinc-800">
              {EVENT_TYPE_LABELS[type]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {needsHighway && (
        <Input
          placeholder="Highway (e.g. SP-330)"
          value={highway}
          onChange={(e) => setHighway(e.target.value)}
          className="h-8 bg-zinc-900 border-zinc-700 text-white text-xs placeholder:text-zinc-500"
        />
      )}

      {needsRegion && (
        <Input
          placeholder="Region (e.g. Campinas)"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="h-8 bg-zinc-900 border-zinc-700 text-white text-xs placeholder:text-zinc-500"
        />
      )}

      {needsEntitySelect && (
        <Select value={entityId} onValueChange={setEntityId}>
          <SelectTrigger className="h-8 bg-zinc-900 border-zinc-700 text-white text-xs">
            <SelectValue placeholder="Select entity..." />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-700">
            {entityOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-white text-xs hover:bg-zinc-800">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {needsMultiplier && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400 shrink-0">Multiplier</label>
          <Input
            type="number"
            min={1}
            value={multiplier}
            onChange={(e) => setMultiplier(Number(e.target.value))}
            className="h-8 bg-zinc-900 border-zinc-700 text-white text-xs w-20"
          />
        </div>
      )}

      {needsDurationTicks && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400 shrink-0">Duration (ticks)</label>
          <Input
            type="number"
            min={1}
            value={durationTicks}
            onChange={(e) => setDurationTicks(Number(e.target.value))}
            className="h-8 bg-zinc-900 border-zinc-700 text-white text-xs w-20"
          />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      <Button
        size="sm"
        disabled={!canSubmit}
        onClick={handleInject}
        className="w-full h-8 bg-red-700 hover:bg-red-600 text-white text-xs"
      >
        {submitting ? "Injecting..." : "Inject"}
      </Button>
    </div>
  );
}

function ActiveEventsList() {
  const activeEvents = useWorldStore((s) => s.activeEvents);
  const tick = useWorldStore((s) => s.tick);
  const [resolvingIds, setResolvingIds] = useState<Set<string>>(new Set());

  async function handleResolve(eventId: string) {
    setResolvingIds((prev) => new Set(prev).add(eventId));
    try {
      await resolveChaosEvent(eventId, tick);
    } catch (err) {
      console.error("Failed to resolve chaos event:", err);
    } finally {
      setResolvingIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  }

  if (activeEvents.length === 0) {
    return (
      <p className="text-xs text-zinc-500 italic">No active events</p>
    );
  }

  return (
    <ScrollArea className="max-h-48">
      <div className="space-y-2">
        {activeEvents.map((event) => {
          const sourceStyle = SOURCE_BADGE_STYLES[event.source] ?? SOURCE_BADGE_STYLES.engine;
          const resolving = resolvingIds.has(event.event_id);

          return (
            <div
              key={event.event_id}
              className="rounded bg-zinc-900/80 p-2 space-y-1"
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-medium text-zinc-200 truncate">
                  {event.event_type}
                </span>
                <Badge className={`text-[10px] px-1.5 py-0 ${sourceStyle.className}`}>
                  {sourceStyle.label}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-zinc-500">
                  Tick {event.tick}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={resolving}
                  onClick={() => handleResolve(event.event_id)}
                  className="h-5 px-2 text-[10px] text-green-400 hover:text-green-300 hover:bg-zinc-800"
                >
                  {resolving ? "..." : "Resolve"}
                </Button>
              </div>
              {event.description && (
                <p className="text-[10px] text-zinc-500 truncate">
                  {event.description}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}

export default function ChaosPanel() {
  const activeEvents = useWorldStore((s) => s.activeEvents);
  const [isOpen, setIsOpen] = useState(false);

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-40 pointer-events-auto">
        <Button
          size="sm"
          onClick={() => setIsOpen(true)}
          className="bg-red-900/90 hover:bg-red-800 text-white text-xs backdrop-blur"
        >
          Chaos ({activeEvents.length} active)
        </Button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-0 right-0 w-80 z-40 pointer-events-auto bg-black/80 backdrop-blur text-white rounded-tl-lg border-t border-l border-zinc-700/50">
      <div className="flex items-center justify-between px-3 py-2">
        <h2 className="text-sm font-bold tracking-wide">Chaos Panel</h2>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setIsOpen(false)}
          className="h-6 w-6 p-0 text-zinc-400 hover:text-white hover:bg-zinc-800"
        >
          X
        </Button>
      </div>

      <Separator className="bg-zinc-700/50" />

      <div className="p-3 space-y-3">
        <InjectEventForm />

        <Separator className="bg-zinc-700/50" />

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Active Events ({activeEvents.length})
          </p>
          <ActiveEventsList />
        </div>
      </div>
    </div>
  );
}
