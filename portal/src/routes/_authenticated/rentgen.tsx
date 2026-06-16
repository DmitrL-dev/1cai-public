import { createFileRoute } from '@tanstack/react-router';
import { useState, useMemo, useCallback, useRef } from 'react';
import { rentgenApi } from '../../lib/api-client';
import { GitBranch, Search, AlertTriangle, Zap } from 'lucide-react';
import {
  type GraphData,
  type GraphNode,
  type GraphLink,
  type NodeType,
} from '../../types/graph';
import GraphCanvas from '../../components/rentgen/GraphCanvas';
import GraphToolbar from '../../components/rentgen/GraphToolbar';
import NodeDetailPanel from '../../components/rentgen/NodeDetailPanel';

export const Route = createFileRoute('/_authenticated/rentgen')({
  component: RentgenPage,
});

interface RawEdge {
  caller: string;
  caller_module: string;
  callee: string;
  callee_module: string;
  depth: number;
}

function RentgenPage() {
  const [entryPoint, setEntryPoint] = useState('');
  const [edges, setEdges] = useState<RawEdge[]>([]);
  const [hasResult, setHasResult] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'flow' | 'impact'>('flow');

  // Graph interaction state
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTypes, setActiveTypes] = useState<Set<NodeType>>(
    new Set<NodeType>(['function', 'procedure', 'query', 'module']),
  );
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<string>>(new Set());

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);

  // ── API call ──
  const handleAnalyze = async () => {
    if (!entryPoint.trim()) return;
    setLoading(true);
    try {
      const apiFn = mode === 'flow' ? rentgenApi.flow : rentgenApi.impact;
      const { data } = await apiFn(entryPoint.trim());
      const rawEdges: RawEdge[] = 'edges' in data ? data.edges : data.callers;
      setEdges(rawEdges);
      setHasResult(true);
      setSelectedNode(null);
      setHighlightNodes(new Set());
      setHighlightLinks(new Set());
    } catch {
      setEdges([]);
      setHasResult(true);
    } finally {
      setLoading(false);
    }
  };

  // ── Transform edges → GraphData ──
  const graphData: GraphData = useMemo(() => {
    if (edges.length === 0) return { nodes: [], links: [] };

    const nodeMap = new Map<string, GraphNode>();

    const getOrCreate = (name: string, mod: string): GraphNode => {
      const id = `${mod}.${name}`;
      let n = nodeMap.get(id);
      if (!n) {
        n = { id, name, type: 'function', module: mod, complexity: 1, calls: [], calledBy: [] };
        nodeMap.set(id, n);
      }
      return n;
    };

    const links: GraphLink[] = [];

    for (const e of edges) {
      const caller = getOrCreate(e.caller, e.caller_module);
      const callee = getOrCreate(e.callee, e.callee_module);

      caller.calls.push(callee.id);
      callee.calledBy.push(caller.id);
      caller.complexity = (caller.complexity ?? 1) + 1;

      links.push({ source: caller.id, target: callee.id, depth: e.depth });
    }

    // Infer node types
    for (const node of nodeMap.values()) {
      if (node.name.startsWith('Запрос')) {
        node.type = 'query';
      } else if (node.calledBy.length === 0) {
        node.type = 'procedure';
      }
    }

    return { nodes: Array.from(nodeMap.values()), links };
  }, [edges]);

  // ── Filter by search + active types ──
  const filteredData: GraphData = useMemo(() => {
    const term = searchTerm.toLowerCase();
    const filtered = graphData.nodes.filter((n) => {
      if (!activeTypes.has(n.type)) return false;
      if (term && !n.name.toLowerCase().includes(term) && !n.module.toLowerCase().includes(term))
        return false;
      return true;
    });
    const ids = new Set(filtered.map((n) => n.id));
    const fLinks = graphData.links.filter((l) => {
      const sId = typeof l.source === 'object' ? (l.source as GraphNode).id : l.source;
      const tId = typeof l.target === 'object' ? (l.target as GraphNode).id : l.target;
      return ids.has(sId) && ids.has(tId);
    });
    return { nodes: filtered, links: fLinks };
  }, [graphData, searchTerm, activeTypes]);

  // ── Callbacks ──
  const handleToggleType = useCallback((type: NodeType) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const handleHighlightChange = useCallback(
    (nodes: Set<string>, links: Set<string>) => {
      setHighlightNodes(nodes);
      setHighlightLinks(links);
    },
    [],
  );

  const handleZoomToFit = useCallback(() => {
    graphRef.current?.zoomToFit?.(400, 40);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedNode(null);
    setHighlightNodes(new Set());
    setHighlightLinks(new Set());
  }, []);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* ── Header ── */}
      <div className="border-b border-slate-700 bg-slate-900 px-6 py-4">
        <div className="flex items-center gap-3 mb-4">
          <GitBranch className="h-6 w-6 text-cyan-400" />
          <h1 className="text-lg font-bold text-slate-100">1С:Рентген</h1>
          <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
            Call Graph Analysis
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Mode toggle */}
          <div className="flex rounded-lg bg-slate-800 p-0.5">
            <button
              onClick={() => setMode('flow')}
              className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                mode === 'flow'
                  ? 'bg-cyan-900/50 text-cyan-300'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Zap className="h-3.5 w-3.5 inline mr-1" />
              Execution Flow
            </button>
            <button
              onClick={() => setMode('impact')}
              className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                mode === 'impact'
                  ? 'bg-orange-900/50 text-orange-300'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
              Impact Analysis
            </button>
          </div>

          {/* Entry point input */}
          <div className="flex-1 flex items-center gap-2">
            <input
              type="text"
              value={entryPoint}
              onChange={(e) => setEntryPoint(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              placeholder={
                mode === 'flow'
                  ? 'Entry point: ОбработкаПроведения, ПередЗаписью...'
                  : 'Target function: ПолучитьЦену, ОбновитьОстатки...'
              }
              className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={handleAnalyze}
              disabled={loading || !entryPoint.trim()}
              className="flex items-center gap-1.5 rounded-lg bg-cyan-900/50 px-4 py-2 text-sm text-cyan-300 hover:bg-cyan-800/50 transition-colors disabled:opacity-40"
            >
              <Search className="h-4 w-4" />
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      {hasResult && filteredData.nodes.length > 0 ? (
        <>
          <GraphToolbar
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            activeTypes={activeTypes}
            onToggleType={handleToggleType}
            nodeCount={filteredData.nodes.length}
            edgeCount={filteredData.links.length}
            onZoomToFit={handleZoomToFit}
          />
          <div className="flex-1 flex relative overflow-hidden bg-slate-950">
            <div className={selectedNode ? 'flex-[3] relative' : 'flex-1 relative'}>
              <GraphCanvas
                data={filteredData}
                selectedNode={selectedNode}
                onNodeSelect={setSelectedNode}
                highlightNodes={highlightNodes}
                highlightLinks={highlightLinks}
                onHighlightChange={handleHighlightChange}
                graphRef={graphRef}
              />
            </div>
            {selectedNode && (
              <NodeDetailPanel node={selectedNode} onClose={handleCloseDetail} />
            )}
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
          <GitBranch className="h-16 w-16 mb-4 opacity-20" />
          {hasResult && edges.length === 0 ? (
            <>
              <p className="text-lg mb-1">No edges found</p>
              <p className="text-sm">Try a different entry point or check the graph is built</p>
            </>
          ) : (
            <>
              <p className="text-lg mb-1">Enter a function name to trace</p>
              <p className="text-sm">
                {mode === 'flow'
                  ? 'Shows the complete call chain from entry point to leaf functions'
                  : 'Shows all functions that depend on the target (reverse graph)'}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
