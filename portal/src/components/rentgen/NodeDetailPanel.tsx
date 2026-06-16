import { X } from 'lucide-react';
import { type GraphNode, NODE_COLORS, NODE_LABELS } from '../../types/graph';

interface NodeDetailPanelProps {
  node: GraphNode | null;
  onClose: () => void;
}

export default function NodeDetailPanel({ node, onClose }: NodeDetailPanelProps) {
  if (!node) return null;

  const typeColor = NODE_COLORS[node.type] ?? '#64748b';
  const typeLabel = NODE_LABELS[node.type] ?? node.type;

  return (
    <div className="w-80 h-full bg-slate-900/95 backdrop-blur border-l border-slate-700 flex flex-col overflow-hidden animate-slide-in-right">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Node Details
        </span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {/* Type badge */}
        <div>
          <span
            className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
            style={{ backgroundColor: `${typeColor}20`, color: typeColor }}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: typeColor }}
            />
            {typeLabel}
          </span>
        </div>

        {/* Name */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
            Name
          </div>
          <div className="text-sm font-bold text-slate-100 font-mono break-all">
            {node.name}
          </div>
        </div>

        {/* Module */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
            Module
          </div>
          <div className="text-sm text-slate-300 font-mono break-all">
            {node.module}
          </div>
        </div>

        {/* Complexity */}
        {node.complexity != null && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              Complexity
            </div>
            <div className="text-sm text-slate-300">{node.complexity}</div>
          </div>
        )}

        {/* Calls (outgoing) */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">
            Calls ({node.calls.length})
          </div>
          {node.calls.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {[...new Set(node.calls)].map((c) => {
                const label = c.includes('.') ? c.split('.').pop() : c;
                return (
                  <span
                    key={c}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-800/50 truncate max-w-full"
                    title={c}
                  >
                    {label}
                  </span>
                );
              })}
            </div>
          ) : (
            <span className="text-xs text-slate-600 italic">Leaf node</span>
          )}
        </div>

        {/* Called by (incoming) */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">
            Called By ({node.calledBy.length})
          </div>
          {node.calledBy.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {[...new Set(node.calledBy)].map((c) => {
                const label = c.includes('.') ? c.split('.').pop() : c;
                return (
                  <span
                    key={c}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-800/50 truncate max-w-full"
                    title={c}
                  >
                    {label}
                  </span>
                );
              })}
            </div>
          ) : (
            <span className="text-xs text-slate-600 italic">Entry point</span>
          )}
        </div>
      </div>
    </div>
  );
}
