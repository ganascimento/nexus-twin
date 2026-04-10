import { useState, useEffect, useCallback } from "react";
import { useWorldStore } from "@/store/worldStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  getSimulationStatus,
  startSimulation,
  stopSimulation,
  advanceTick,
  setSimulationSpeed,
} from "@/lib/api";

type SimulationState = "running" | "stopped" | "unknown";

function formatSimulatedTimestamp(raw: string): string {
  if (!raw) return "--";
  try {
    return new Date(raw).toLocaleString();
  } catch {
    return raw;
  }
}

export default function StatsBar() {
  const tick = useWorldStore((s) => s.tick);
  const simulatedTimestamp = useWorldStore((s) => s.simulatedTimestamp);
  const isConnected = useWorldStore((s) => s.isConnected);
  const activeEvents = useWorldStore((s) => s.activeEvents);
  const factories = useWorldStore((s) => s.factories);
  const warehouses = useWorldStore((s) => s.warehouses);
  const stores = useWorldStore((s) => s.stores);
  const trucks = useWorldStore((s) => s.trucks);

  const [simulationStatus, setSimulationStatus] = useState<SimulationState>("unknown");
  const [tickInterval, setTickInterval] = useState(10);

  useEffect(() => {
    getSimulationStatus()
      .then((data) => {
        setSimulationStatus(data.status);
        setTickInterval(data.tick_interval_seconds);
      })
      .catch(() => setSimulationStatus("unknown"));
  }, []);

  const criticalCount =
    factories.filter((f) => f.status !== "operating").length +
    warehouses.filter((w) => w.status !== "operating").length +
    stores.filter((s) => s.status !== "open").length +
    trucks.filter((t) => t.status === "broken").length;

  const handleToggleSimulation = useCallback(async () => {
    try {
      if (simulationStatus === "running") {
        await stopSimulation();
        setSimulationStatus("stopped");
      } else {
        await startSimulation();
        setSimulationStatus("running");
      }
    } catch {
      // keep current state on failure
    }
  }, [simulationStatus]);

  const handleAdvanceTick = useCallback(async () => {
    try {
      await advanceTick();
    } catch {
      // ignore
    }
  }, []);

  const handleApplySpeed = useCallback(async () => {
    try {
      await setSimulationSpeed(tickInterval);
    } catch {
      // ignore
    }
  }, [tickInterval]);

  return (
    <div className="pointer-events-auto fixed top-0 left-0 right-0 z-50 flex items-center justify-between bg-black/80 backdrop-blur px-4 py-2 text-white text-sm">
      {/* Left section - World info */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-gray-400">Tick</span>
          <span className="font-mono font-bold">{tick}</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-gray-400">Time</span>
          <span className="font-mono">{formatSimulatedTimestamp(simulatedTimestamp)}</span>
        </div>

        <Badge className={isConnected ? "bg-green-600" : "bg-red-600"}>
          <span
            className={`mr-1.5 inline-block h-2 w-2 rounded-full ${
              isConnected ? "bg-green-300" : "bg-red-300"
            }`}
          />
          {isConnected ? "Connected" : "Disconnected"}
        </Badge>
      </div>

      {/* Center section - Health indicators */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="text-yellow-400">&#9888;</span>
          <span>{activeEvents.length} chaos</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className={criticalCount > 0 ? "text-red-400" : "text-gray-400"}>&#9679;</span>
          <span className={criticalCount > 0 ? "text-red-300" : "text-gray-300"}>
            {criticalCount} critical
          </span>
        </div>
      </div>

      {/* Right section - Simulation controls */}
      <div className="flex items-center gap-2">
        <Badge
          className={
            simulationStatus === "running"
              ? "bg-green-700"
              : simulationStatus === "stopped"
                ? "bg-gray-600"
                : "bg-yellow-700"
          }
        >
          {simulationStatus}
        </Badge>

        <Button
          size="xs"
          variant="secondary"
          onClick={handleToggleSimulation}
        >
          {simulationStatus === "running" ? "Stop" : "Start"}
        </Button>

        <Button
          size="xs"
          variant="outline"
          onClick={handleAdvanceTick}
          disabled={simulationStatus === "running"}
        >
          Tick
        </Button>

        <div className="flex items-center gap-1 ml-2">
          <Input
            type="number"
            min={10}
            value={tickInterval}
            onChange={(e) => setTickInterval(Math.max(10, Number(e.target.value)))}
            className="h-7 w-16 bg-white/10 border-white/20 text-white text-xs px-2"
          />
          <span className="text-gray-400 text-xs">s</span>
          <Button size="xs" variant="ghost" onClick={handleApplySpeed}>
            Apply
          </Button>
        </div>
      </div>
    </div>
  );
}
