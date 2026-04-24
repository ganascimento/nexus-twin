import { useEffect, useRef, useState } from "react";
import { Marker } from "react-map-gl/maplibre";
import { useWorldStore } from "../store/worldStore";
import type { WorldStoreState } from "../store/worldStore";
import type { AgentType } from "../types/world";

type AnimationKind =
  | "order_email"
  | "accept_gem"
  | "refuse_gem"
  | "breakdown_sign"
  | "confirm_check"
  | "send_box"
  | "reject_x"
  | "maintenance_wrench";

interface FloatingAnimation {
  id: string;
  kind: AnimationKind;
  lng: number;
  lat: number;
  addedAt: number;
}

const DURATION_MS = 1800;

const FLOATING_KEYFRAMES = `
@keyframes fa-rise {
  0%   { transform: translate(24px, -24px) scale(0.6); opacity: 0; }
  20%  { transform: translate(24px, -34px) scale(1.05); opacity: 1; }
  80%  { transform: translate(24px, -58px) scale(1); opacity: 1; }
  100% { transform: translate(24px, -72px) scale(0.95); opacity: 0; }
}
@keyframes fa-drop {
  0%   { transform: translate(24px, -34px) scale(0.6); opacity: 0; }
  25%  { transform: translate(24px, -24px) scale(1.05); opacity: 1; }
  80%  { transform: translate(24px, -10px) scale(1); opacity: 1; }
  100% { transform: translate(24px, 4px) scale(0.95); opacity: 0; }
}
@keyframes fa-pop {
  0%   { transform: translate(24px, -24px) scale(0.3); opacity: 0; }
  30%  { transform: translate(24px, -24px) scale(1.2); opacity: 1; }
  70%  { transform: translate(24px, -24px) scale(1); opacity: 1; }
  100% { transform: translate(24px, -24px) scale(1); opacity: 0; }
}
@keyframes fa-shake {
  0%   { transform: translate(24px, -24px) rotate(0); opacity: 0; }
  10%  { transform: translate(24px, -24px) rotate(0); opacity: 1; }
  25%  { transform: translate(22px, -24px) rotate(-6deg); }
  50%  { transform: translate(26px, -24px) rotate(6deg); }
  75%  { transform: translate(22px, -24px) rotate(-4deg); }
  90%  { transform: translate(24px, -24px) rotate(0); opacity: 1; }
  100% { transform: translate(24px, -24px) rotate(0); opacity: 0; }
}
`;

const ACTION_TO_KIND: Record<string, AnimationKind> = {
  order_replenishment: "order_email",
  request_resupply: "order_email",
  accept_contract: "accept_gem",
  refuse_contract: "refuse_gem",
  alert_breakdown: "breakdown_sign",
  confirm_order: "confirm_check",
  send_stock: "send_box",
  reject_order: "reject_x",
  request_maintenance: "maintenance_wrench",
};

const KIND_TO_ICON: Record<AnimationKind, string> = {
  order_email: "📧",
  accept_gem: "💚",
  refuse_gem: "⚠️",
  breakdown_sign: "🛠️",
  confirm_check: "✅",
  send_box: "📦",
  reject_x: "❌",
  maintenance_wrench: "🔧",
};

const KIND_TO_BG: Record<AnimationKind, string> = {
  order_email: "rgba(14, 165, 233, 0.92)",
  accept_gem: "rgba(16, 185, 129, 0.92)",
  refuse_gem: "rgba(245, 158, 11, 0.92)",
  breakdown_sign: "rgba(220, 38, 38, 0.92)",
  confirm_check: "rgba(5, 150, 105, 0.92)",
  send_box: "rgba(99, 102, 241, 0.92)",
  reject_x: "rgba(225, 29, 72, 0.92)",
  maintenance_wrench: "rgba(249, 115, 22, 0.92)",
};

const KIND_TO_ANIMATION: Record<AnimationKind, string> = {
  order_email: "fa-rise",
  accept_gem: "fa-pop",
  refuse_gem: "fa-drop",
  breakdown_sign: "fa-shake",
  confirm_check: "fa-pop",
  send_box: "fa-rise",
  reject_x: "fa-drop",
  maintenance_wrench: "fa-pop",
};

function findEntityPosition(
  entityId: string,
  agentType: AgentType | undefined,
  state: WorldStoreState,
): [number, number] | null {
  switch (agentType) {
    case "factory": {
      const f = state.factories.find((x) => x.id === entityId);
      return f ? [f.lng, f.lat] : null;
    }
    case "warehouse": {
      const w = state.warehouses.find((x) => x.id === entityId);
      return w ? [w.lng, w.lat] : null;
    }
    case "store": {
      const s = state.stores.find((x) => x.id === entityId);
      return s ? [s.lng, s.lat] : null;
    }
    case "truck": {
      const t = state.trucks.find((x) => x.id === entityId);
      return t ? [t.current_lng, t.current_lat] : null;
    }
    default:
      return null;
  }
}

export default function FloatingAnimations() {
  const recentDecisions = useWorldStore((s) => s.recentDecisions);
  const factories = useWorldStore((s) => s.factories);
  const warehouses = useWorldStore((s) => s.warehouses);
  const stores = useWorldStore((s) => s.stores);
  const trucks = useWorldStore((s) => s.trucks);
  const [animations, setAnimations] = useState<FloatingAnimation[]>([]);
  const counterRef = useRef(0);
  const seenKeysRef = useRef<Set<string>>(new Set());

  if (recentDecisions.length > 0) {
    const state = { factories, warehouses, stores, trucks } as WorldStoreState;
    const created: FloatingAnimation[] = [];
    for (const d of recentDecisions) {
      const key = `${d.tick}|${d.entity_id}|${d.action}`;
      if (seenKeysRef.current.has(key)) continue;
      seenKeysRef.current.add(key);
      const kind = ACTION_TO_KIND[d.action];
      if (!kind) continue;
      const pos = findEntityPosition(d.entity_id, d.agent_type, state);
      if (!pos) continue;
      counterRef.current += 1;
      created.push({
        id: `${d.tick}-${d.entity_id}-${d.action}-${counterRef.current}`,
        kind,
        lng: pos[0],
        lat: pos[1],
        addedAt: Date.now(),
      });
    }
    if (created.length > 0) {
      queueMicrotask(() => setAnimations((prev) => [...prev, ...created]));
    }
    if (seenKeysRef.current.size > 500) {
      const keep = new Set(
        recentDecisions.map((d) => `${d.tick}|${d.entity_id}|${d.action}`),
      );
      seenKeysRef.current = keep;
    }
  }

  useEffect(() => {
    if (animations.length === 0) return;
    const timer = window.setTimeout(() => {
      const cutoff = Date.now() - DURATION_MS;
      setAnimations((prev) => prev.filter((a) => a.addedAt > cutoff));
    }, DURATION_MS + 100);
    return () => window.clearTimeout(timer);
  }, [animations]);

  return (
    <>
      <style>{FLOATING_KEYFRAMES}</style>
      {animations.map((a) => (
        <Marker
          key={a.id}
          longitude={a.lng}
          latitude={a.lat}
          anchor="center"
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              backgroundColor: KIND_TO_BG[a.kind],
              boxShadow:
                "0 0 0 2px #ffffff, 0 4px 10px rgba(0,0,0,0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              lineHeight: 1,
              pointerEvents: "none",
              animation: `${KIND_TO_ANIMATION[a.kind]} ${DURATION_MS}ms ease-out forwards`,
              willChange: "transform, opacity",
            }}
          >
            <span aria-hidden="true">{KIND_TO_ICON[a.kind]}</span>
          </div>
        </Marker>
      ))}
    </>
  );
}
