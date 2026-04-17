export interface WorkflowNode {
  id: string;
  type: "action" | "condition" | "loop" | "group";
  position: { x: number; y: number };
  data: NodeData;
  selected?: boolean;
}

export interface ActionData {
  action: string;
  selector?: string;
  value?: string;
  url?: string;
  timeout?: number;
}

export interface ConditionData {
  condition: string;
  selector?: string;
}

export interface LoopData {
  loopType: "items" | "count" | "while";
  selector?: string;
  count?: number;
  condition?: string;
  variable?: string;
  max?: number;
}

export type NodeData = ActionData | ConditionData | LoopData | Record<string, unknown>;

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface Workflow {
  id: string;
  name: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  createdAt: string;
  updatedAt: string;
}
