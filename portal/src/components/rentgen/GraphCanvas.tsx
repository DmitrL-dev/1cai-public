import ForceGraph2D from 'react-force-graph-2d';
import { useRef, useEffect, useCallback, useState } from 'react';
import {
  type GraphData,
  type GraphNode,
  NODE_COLORS,
} from '../../types/graph';

interface GraphCanvasProps {
  data: GraphData;
  width?: number;
  height?: number;
  selectedNode: GraphNode | null;
  onNodeSelect: (node: GraphNode | null) => void;
  highlightNodes: Set<string>;
  highlightLinks: Set<string>;
  onHighlightChange: (nodes: Set<string>, links: Set<string>) => void;
  graphRef?: { current: any }; // eslint-disable-line @typescript-eslint/no-explicit-any
}

function getLinkKey(link: any): string { // eslint-disable-line @typescript-eslint/no-explicit-any
  const sId = typeof link.source === 'object' ? link.source?.id : link.source;
  const tId = typeof link.target === 'object' ? link.target?.id : link.target;
  return `${sId}__${tId}`;
}

export default function GraphCanvas({
  data,
  width,
  height,
  selectedNode,
  onNodeSelect,
  highlightNodes,
  highlightLinks,
  onHighlightChange,
  graphRef: externalRef,
}: GraphCanvasProps) {
  const internalRef = useRef<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const fgRef = externalRef ?? internalRef;
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: width ?? 800, h: height ?? 600 });

  // ── Auto-size to container ──
  useEffect(() => {
    if (width !== undefined && height !== undefined) {
      setDims({ w: width, h: height });
      return;
    }
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width: cw, height: ch } = entries[0].contentRect;
      if (cw > 0 && ch > 0) setDims({ w: cw, h: ch });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [width, height]);

  // ── Force tuning ──
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force('charge')?.strength(-120);
    fg.d3Force('link')?.distance((link: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      const sMod = typeof link.source === 'object' ? link.source?.module : '';
      const tMod = typeof link.target === 'object' ? link.target?.module : '';
      return sMod && tMod && sMod === tMod ? 60 : 150;
    });
  }, [fgRef, data]);

  // ── Zoom to fit on data change ──
  useEffect(() => {
    if (data.nodes.length > 0) {
      setTimeout(() => fgRef.current?.zoomToFit?.(400, 40), 300);
    }
  }, [fgRef, data]);

  // ── Node click → highlight neighbors ──
  const handleNodeClick = useCallback(
    (node: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      const gn = node as GraphNode;
      onNodeSelect(gn);

      const nNodes = new Set<string>([gn.id]);
      const nLinks = new Set<string>();

      for (const link of data.links) {
        const sId = typeof link.source === 'object' ? (link.source as GraphNode).id : link.source;
        const tId = typeof link.target === 'object' ? (link.target as GraphNode).id : link.target;
        if (sId === gn.id || tId === gn.id) {
          nNodes.add(sId);
          nNodes.add(tId);
          nLinks.add(`${sId}__${tId}`);
        }
      }
      onHighlightChange(nNodes, nLinks);
    },
    [data.links, onNodeSelect, onHighlightChange],
  );

  // ── Background click → clear ──
  const handleBgClick = useCallback(() => {
    onNodeSelect(null);
    onHighlightChange(new Set(), new Set());
  }, [onNodeSelect, onHighlightChange]);

  // ── Custom node renderer ──
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      const gn = node as GraphNode;
      const x = node.x as number;
      const y = node.y as number;
      const size = Math.sqrt(gn.complexity ?? 1) * 3 + 4;
      const color = NODE_COLORS[gn.type] ?? '#64748b';
      const isHl = highlightNodes.size === 0 || highlightNodes.has(gn.id);

      ctx.globalAlpha = isHl ? 1 : 0.15;

      // Node circle
      ctx.beginPath();
      ctx.arc(x, y, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Selected ring
      if (selectedNode?.id === gn.id) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }

      // Label (only when zoomed in)
      if (globalScale > 0.7) {
        const fontSize = 11 / globalScale;
        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = 'rgba(226,232,240,0.9)';
        ctx.fillText(gn.name, x, y + size + 2 / globalScale);
      }

      ctx.globalAlpha = 1;
    },
    [highlightNodes, selectedNode],
  );

  // ── Link color ──
  const linkColor = useCallback(
    (link: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      if (highlightLinks.size === 0) return 'rgba(100,116,139,0.3)';
      return highlightLinks.has(getLinkKey(link))
        ? 'rgba(56,189,248,0.8)'
        : 'rgba(100,116,139,0.08)';
    },
    [highlightLinks],
  );

  // ── Particles on highlighted links ──
  const linkParticles = useCallback(
    (link: any) => (highlightLinks.has(getLinkKey(link)) ? 4 : 0), // eslint-disable-line @typescript-eslint/no-explicit-any
    [highlightLinks],
  );

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        width={dims.w}
        height={dims.h}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        linkColor={linkColor}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkCurvature={0.12}
        linkDirectionalParticles={linkParticles}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleSpeed={0.005}
        onNodeClick={handleNodeClick}
        onBackgroundClick={handleBgClick}
        backgroundColor="transparent"
        nodeId="id"
      />
    </div>
  );
}
