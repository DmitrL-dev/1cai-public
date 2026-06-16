export type NodeType = 'function' | 'procedure' | 'query' | 'module';

export interface GraphNode {
  id: string;
  name: string;
  type: NodeType;
  module: string;
  complexity?: number;
  isExport?: boolean;
  calls: string[];
  calledBy: string[];
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  depth?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export const NODE_COLORS: Record<NodeType, string> = {
  function:  '#3b82f6', // blue-500
  procedure: '#10b981', // emerald-500
  query:     '#f59e0b', // amber-500
  module:    '#a855f7', // purple-500
};

export const NODE_LABELS: Record<NodeType, string> = {
  function:  'Функция',
  procedure: 'Процедура',
  query:     'Запрос',
  module:    'Модуль',
};
