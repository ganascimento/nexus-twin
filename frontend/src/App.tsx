import WorldMap from "./map/WorldMap";
import { useWorldSocket } from "./hooks/useWorldSocket";

export default function App() {
  useWorldSocket();

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden" }}>
      <WorldMap />
      {/* HUD overlay — feature 18 */}
    </div>
  );
}
