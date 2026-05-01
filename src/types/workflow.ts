export type WorkflowNodeKind = 'action' | 'condition' | 'loop' | 'group';

export interface WorkflowPosition {
  x: number;
  y: number;
}

export interface WorkflowNodeSettings {
  onError?: 'inherit' | 'stop' | 'continue' | 'retry' | 'fallback';
  retryOnFail?: boolean;
  retryCount?: number;
  retryInterval?: number;
  note?: string;
  disabled?: boolean;
  [key: string]: unknown;
}

export interface WorkflowNodeRuntime {
  sessionId?: string;
  [key: string]: unknown;
}

export interface CanonicalWorkflowNode {
  id: string;
  kind: WorkflowNodeKind;
  action?: string;
  position: WorkflowPosition;
  data: Record<string, unknown>;
  settings?: WorkflowNodeSettings;
  runtime?: WorkflowNodeRuntime;
  selected?: boolean;
}

export interface WorkflowNode {
  id: string;
  type: WorkflowNodeKind;
  position: WorkflowPosition;
  data: NodeData;
  selected?: boolean;
}

export interface ActionData {
  action: string;
  selector?: string;
  value?: string;
  url?: string;
  timeout?: number;
  sessionId?: string;
}

export interface ConditionData {
  condition: string;
  selector?: string;
  sessionId?: string;
}

export interface LoopData {
  loopType: 'items' | 'count' | 'while' | 'elements';
  selector?: string;
  count?: number;
  condition?: string;
  variable?: string;
  max?: number;
  sessionId?: string;
}

export type NodeData = ActionData | ConditionData | LoopData | Record<string, unknown>;

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  label?: string;
}

export interface CanonicalWorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  label?: string;
}

export interface Workflow {
  id: string;
  name: string;
  nodes: CanonicalWorkflowNode[];
  edges: CanonicalWorkflowEdge[];
  createdAt?: string;
  updatedAt?: string;
}
