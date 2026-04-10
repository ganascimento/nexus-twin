import { useEffect, useRef } from "react";
import { useWorldStore } from "../store/worldStore";
import type { WSMessage, WorldStatePayload, AgentDecisionPayload, EventPayload } from "../types/world";

const PING_INTERVAL_MS = 30000;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

export function useWorldSocket(): void {
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS);

  useEffect(() => {
    let isCleanedUp = false;
    let ws: WebSocket | null = null;
    let pingInterval: ReturnType<typeof setInterval> | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    function clearPingInterval() {
      if (pingInterval !== null) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
    }

    function clearReconnectTimeout() {
      if (reconnectTimeout !== null) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
    }

    function connect() {
      if (isCleanedUp) return;

      const wsUrl =
        (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/^http/, "ws") + "/ws";

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        useWorldStore.getState().setConnected(true);
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS;

        pingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (event: MessageEvent) => {
        const message = JSON.parse(event.data as string) as WSMessage;
        const store = useWorldStore.getState();

        switch (message.channel) {
          case "world_state":
            store.setWorldState(message.payload as WorldStatePayload);
            break;
          case "agent_decisions":
            store.addDecision(message.payload as AgentDecisionPayload);
            break;
          case "events":
            store.updateEvent(message.payload as EventPayload);
            break;
        }
      };

      ws.onclose = () => {
        useWorldStore.getState().setConnected(false);
        clearPingInterval();

        if (!isCleanedUp) {
          reconnectTimeout = setTimeout(() => {
            reconnectDelayRef.current = Math.min(
              reconnectDelayRef.current * 2,
              MAX_RECONNECT_DELAY_MS,
            );
            connect();
          }, reconnectDelayRef.current);
        }
      };

      ws.onerror = (error: Event) => {
        console.error("WebSocket error:", error);
      };
    }

    connect();

    return () => {
      isCleanedUp = true;
      clearPingInterval();
      clearReconnectTimeout();
      if (ws) {
        ws.close();
      }
    };
  }, []);
}
