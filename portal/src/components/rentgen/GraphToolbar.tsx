import { Search, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { type NodeType, NODE_COLORS, NODE_LABELS } from '../../types/graph';

interface GraphToolbarProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  activeTypes: Set<NodeType>;
  onToggleType: (type: NodeType) => void;
  nodeCount: number;
  edgeCount: number;
  onZoomToFit: () => void;
}

const ALL_TYPES: NodeType[] = ['function', 'procedure', 'query', 'module'];

export default function GraphToolbar({
  searchTerm,
  onSearchChange,
  activeTypes,
  onToggleType,
  nodeCount,
  edgeCount,
  onZoomToFit,
}: GraphToolbarProps) {
  return (
    <div className="bg-slate-900 border-b border-slate-700 px-4 py-2 flex items-center gap-4 flex-wrap">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Filter nodes..."
          className="bg-slate-800 border border-slate-700 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-600 w-52"
        />
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-slate-700" />

      {/* Type filters */}
      <div className="flex items-center gap-1.5">
        {ALL_TYPES.map((t) => {
          const active = activeTypes.has(t);
          return (
            <button
              key={t}
              onClick={() => onToggleType(t)}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md transition-colors ${
                active
                  ? 'bg-slate-700 text-slate-200'
                  : 'bg-slate-800/50 text-slate-500 hover:text-slate-400'
              }`}
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  backgroundColor: active ? NODE_COLORS[t] : '#475569',
                }}
              />
              {NODE_LABELS[t]}
            </button>
          );
        })}
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-slate-700" />

      {/* Zoom controls */}
      <div className="flex items-center gap-1">
        <button
          onClick={onZoomToFit}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
          title="Fit to view"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => {
            /* zoom handled by graph scroll */
          }}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
          title="Zoom in"
        >
          <ZoomIn className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => {
            /* zoom handled by graph scroll */
          }}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
          title="Zoom out"
        >
          <ZoomOut className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Stats */}
      <div className="flex items-center gap-3 text-xs text-slate-500">
        <span>
          <span className="text-slate-300 font-medium">{nodeCount}</span> nodes
        </span>
        <span>
          <span className="text-slate-300 font-medium">{edgeCount}</span> edges
        </span>
      </div>
    </div>
  );
}
