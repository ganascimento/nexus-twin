import { useWorldStore } from "../store/worldStore";
import { useInspect } from "../hooks/useInspect";
import { ScrollArea } from "../components/ui/scroll-area";
import { Badge } from "../components/ui/badge";
import type { AgentType, EntityType } from "../types/world";

const AGENT_TYPE_COLORS: Record<AgentType, string> = {
  factory: "bg-blue-600",
  warehouse: "bg-yellow-600",
  store: "bg-green-600",
  truck: "bg-cyan-600",
  master: "bg-purple-600",
};

const AGENT_TYPE_ICONS: Record<AgentType, string> = {
  factory: "🏭",
  warehouse: "📦",
  store: "🏪",
  truck: "🚚",
  master: "🎯",
};

const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  factory: "Fábrica",
  warehouse: "Armazém",
  store: "Loja",
  truck: "Caminhão",
  master: "Master",
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

const DISPLAY_LIMIT = 50;

export default function AgentLog() {
  const recentDecisions = useWorldStore((s) => s.recentDecisions);
  const selectEntity = useInspect((s) => s.selectEntity);

  const visibleDecisions = recentDecisions.slice(0, DISPLAY_LIMIT);

  return (
    <div className="fixed bottom-0 left-0 z-40 w-[28rem] max-h-[26rem] flex flex-col bg-black/80 backdrop-blur text-white pointer-events-auto rounded-tr-lg border-t border-r border-white/10">
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 shrink-0">
        <h2 className="text-sm font-semibold">
          Agent Decisions ({recentDecisions.length})
        </h2>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-3 py-1 space-y-1">
          {visibleDecisions.map((decision, index) => (
            <button
              key={`${decision.tick}-${decision.entity_id}-${decision.action}-${index}`}
              type="button"
              className="w-full text-left px-2 py-1.5 rounded hover:bg-white/10 transition-colors flex items-start gap-2"
              onClick={() => {
                if (decision.agent_type !== "master") {
                  selectEntity(
                    decision.entity_id,
                    decision.agent_type as EntityType
                  );
                }
              }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-base leading-none" aria-hidden="true">
                    {AGENT_TYPE_ICONS[decision.agent_type]}
                  </span>
                  <Badge className={AGENT_TYPE_COLORS[decision.agent_type]}>
                    {AGENT_TYPE_LABELS[decision.agent_type]}
                  </Badge>
                  <span className="text-xs font-bold truncate">
                    {decision.entity_name || decision.entity_id}
                  </span>
                </div>
                <p className="text-xs text-white/60 mt-0.5">
                  <span className="text-white/80">
                    {ACTION_LABELS[decision.action] ?? decision.action}
                  </span>
                  <span className="text-white/30 ml-1 font-mono">
                    ({decision.entity_id})
                  </span>
                </p>
                {decision.summary && (
                  <p className="text-xs text-white/70 mt-0.5 line-clamp-2 italic">
                    {decision.summary}
                  </p>
                )}
              </div>
              <span className="text-[10px] text-white/40 whitespace-nowrap shrink-0 pt-0.5">
                T{decision.tick}
              </span>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
