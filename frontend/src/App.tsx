import WorldMap from "./map/WorldMap";
import { useWorldSocket } from "./hooks/useWorldSocket";
import StatsBar from "./hud/StatsBar";
import InspectPanel from "./hud/InspectPanel";
import AgentLog from "./hud/AgentLog";
import ChaosPanel from "./hud/ChaosPanel";
import WorldManagement from "./hud/WorldManagement";

export default function App() {
  useWorldSocket();

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden" }}>
      <WorldMap />
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <StatsBar />
        <InspectPanel />
        <AgentLog />
        <ChaosPanel />
        <WorldManagement />
      </div>
    </div>
  );
}
