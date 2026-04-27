import type { Edge, Node } from "@vue-flow/core";
import type {
  CanonicalWorkflowEdge,
  CanonicalWorkflowNode,
  Workflow,
  WorkflowNodeKind,
  WorkflowNodeRuntime,
  WorkflowNodeSettings,
} from "../types/workflow";

type UnknownRecord = Record<string, unknown>;

const NODE_KINDS = new Set<WorkflowNodeKind>(["action", "condition", "loop", "group"]);

const ALLOWED_NODE_KEYS = new Set([
  "id",
  "kind",
  "action",
  "position",
  "data",
  "settings",
  "runtime",
  "selected",
]);

const ALLOWED_EDGE_KEYS = new Set([
  "id",
  "source",
  "target",
  "sourceHandle",
  "targetHandle",
  "label",
]);

const ALLOWED_WORKFLOW_KEYS = new Set([
  "id",
  "name",
  "nodes",
  "edges",
  "createdAt",
  "updatedAt",
]);

export class WorkflowSchemaError extends Error {
  constructor(message: string, public readonly path: string) {
    super(`${message} (at ${path})`);
    this.name = "WorkflowSchemaError";
  }
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function isNodeKind(value: unknown): value is WorkflowNodeKind {
  return typeof value === "string" && NODE_KINDS.has(value as WorkflowNodeKind);
}

// ---------- Validation ----------

export function validateCanonicalNode(raw: unknown, path = "node"): CanonicalWorkflowNode {
  if (!isRecord(raw)) {
    throw new WorkflowSchemaError("expected object", path);
  }
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_NODE_KEYS.has(key)) {
      throw new WorkflowSchemaError(
        `unknown field "${key}" — canonical nodes only allow ${[...ALLOWED_NODE_KEYS].join(", ")}; legacy fields must be migrated via migrateLegacyWorkflow()`,
        path,
      );
    }
  }
  const id = optionalString(raw.id);
  if (!id) throw new WorkflowSchemaError("missing or empty id", path);
  if (!isNodeKind(raw.kind)) {
    throw new WorkflowSchemaError(`invalid kind ${JSON.stringify(raw.kind)}`, `${path}.kind`);
  }
  if (!isRecord(raw.position) || typeof raw.position.x !== "number" || typeof raw.position.y !== "number") {
    throw new WorkflowSchemaError("position must be { x: number, y: number }", `${path}.position`);
  }
  if (!isRecord(raw.data)) {
    throw new WorkflowSchemaError("data must be an object", `${path}.data`);
  }
  if (raw.action !== undefined && typeof raw.action !== "string") {
    throw new WorkflowSchemaError("action must be a string", `${path}.action`);
  }
  if (raw.settings !== undefined && !isRecord(raw.settings)) {
    throw new WorkflowSchemaError("settings must be an object", `${path}.settings`);
  }
  if (raw.runtime !== undefined && !isRecord(raw.runtime)) {
    throw new WorkflowSchemaError("runtime must be an object", `${path}.runtime`);
  }
  if (raw.selected !== undefined && typeof raw.selected !== "boolean") {
    throw new WorkflowSchemaError("selected must be boolean", `${path}.selected`);
  }
  return raw as unknown as CanonicalWorkflowNode;
}

export function validateCanonicalEdge(raw: unknown, path = "edge"): CanonicalWorkflowEdge {
  if (!isRecord(raw)) throw new WorkflowSchemaError("expected object", path);
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_EDGE_KEYS.has(key)) {
      throw new WorkflowSchemaError(`unknown field "${key}"`, path);
    }
  }
  const id = optionalString(raw.id);
  const source = optionalString(raw.source);
  const target = optionalString(raw.target);
  if (!id || !source || !target) {
    throw new WorkflowSchemaError("edge requires id, source, target", path);
  }
  return raw as unknown as CanonicalWorkflowEdge;
}

export function validateCanonicalWorkflow(raw: unknown): Workflow {
  if (!isRecord(raw)) throw new WorkflowSchemaError("expected object", "workflow");
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_WORKFLOW_KEYS.has(key)) {
      throw new WorkflowSchemaError(`unknown field "${key}"`, "workflow");
    }
  }
  if (!optionalString(raw.id)) {
    throw new WorkflowSchemaError("workflow id must be non-empty string", "workflow.id");
  }
  if (typeof raw.name !== "string") {
    throw new WorkflowSchemaError("workflow name must be a string", "workflow.name");
  }
  if (!Array.isArray(raw.nodes)) {
    throw new WorkflowSchemaError("workflow.nodes must be an array", "workflow.nodes");
  }
  if (!Array.isArray(raw.edges)) {
    throw new WorkflowSchemaError("workflow.edges must be an array", "workflow.edges");
  }
  raw.nodes.forEach((n, i) => validateCanonicalNode(n, `workflow.nodes[${i}]`));
  raw.edges.forEach((e, i) => validateCanonicalEdge(e, `workflow.edges[${i}]`));
  return raw as unknown as Workflow;
}

// ---------- Legacy migration (explicit, opt-in) ----------

const LEGACY_NODE_TOP_KEYS = new Set([
  ...ALLOWED_NODE_KEYS,
  "type",
  "kind",
  "session_id",
  "sessionId",
  "children",
  "elseChildren",
]);

function migrateLegacyNode(raw: unknown, path: string): CanonicalWorkflowNode {
  if (!isRecord(raw)) {
    throw new WorkflowSchemaError("expected object", path);
  }
  const sourceData = isRecord(raw.data) ? { ...raw.data } : {};

  const kindCandidate = raw.kind ?? raw.type ?? sourceData.kind;
  const kind: WorkflowNodeKind = isNodeKind(kindCandidate) ? kindCandidate : "action";

  const data: UnknownRecord = { ...sourceData };
  delete data.action;
  delete data.settings;
  delete data.runtime;
  delete data.sessionId;
  delete data.session_id;
  delete data.kind;

  const action = optionalString(raw.action) ?? optionalString(sourceData.action);

  const settingsRaw = isRecord(raw.settings) ? raw.settings : isRecord(sourceData.settings) ? sourceData.settings : undefined;
  const settings: WorkflowNodeSettings | undefined = settingsRaw ? { ...settingsRaw } : undefined;

  const runtimeRaw = isRecord(raw.runtime) ? raw.runtime : isRecord(sourceData.runtime) ? sourceData.runtime : undefined;
  const runtime: WorkflowNodeRuntime = runtimeRaw ? { ...runtimeRaw } : {};
  const sessionId = optionalString(raw.sessionId)
    ?? optionalString(raw.session_id)
    ?? optionalString(sourceData.sessionId)
    ?? optionalString(sourceData.session_id)
    ?? optionalString(runtime.sessionId);
  if (sessionId) runtime.sessionId = sessionId;

  // Legacy: top-level extras (selector, url, value, etc.) get tucked into data.
  for (const [key, value] of Object.entries(raw)) {
    if (!LEGACY_NODE_TOP_KEYS.has(key) && !(key in data)) {
      data[key] = value;
    }
  }

  // Legacy: children at top level move under data.
  if (Array.isArray(raw.children)) {
    data.children = raw.children.map((c, i) => migrateLegacyNode(c, `${path}.children[${i}]`));
  } else if (Array.isArray(sourceData.children)) {
    data.children = sourceData.children.map((c, i) => migrateLegacyNode(c, `${path}.data.children[${i}]`));
  }
  if (Array.isArray(raw.elseChildren)) {
    data.elseChildren = raw.elseChildren.map((c, i) => migrateLegacyNode(c, `${path}.elseChildren[${i}]`));
  } else if (Array.isArray(sourceData.elseChildren)) {
    data.elseChildren = sourceData.elseChildren.map((c, i) => migrateLegacyNode(c, `${path}.data.elseChildren[${i}]`));
  }

  const node: CanonicalWorkflowNode = {
    id: String(raw.id ?? `node_${Date.now()}`),
    kind,
    position: isRecord(raw.position)
      ? { x: Number(raw.position.x ?? 0), y: Number(raw.position.y ?? 0) }
      : { x: 0, y: 0 },
    data,
  };
  if (action) node.action = action;
  if (settings && Object.keys(settings).length) node.settings = settings;
  if (Object.keys(runtime).length) node.runtime = runtime;
  if (typeof raw.selected === "boolean") node.selected = raw.selected;
  return node;
}

function migrateLegacyEdge(raw: unknown, path: string): CanonicalWorkflowEdge {
  if (!isRecord(raw)) throw new WorkflowSchemaError("expected object", path);
  const id = optionalString(raw.id) ?? `edge_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
  const source = optionalString(raw.source);
  const target = optionalString(raw.target);
  if (!source || !target) throw new WorkflowSchemaError("edge requires source and target", path);
  const edge: CanonicalWorkflowEdge = { id, source, target };
  if (typeof raw.sourceHandle === "string" || raw.sourceHandle === null) {
    edge.sourceHandle = raw.sourceHandle as string | null;
  }
  if (typeof raw.targetHandle === "string" || raw.targetHandle === null) {
    edge.targetHandle = raw.targetHandle as string | null;
  }
  if (typeof raw.label === "string") edge.label = raw.label;
  return edge;
}

/**
 * Migrate a workflow JSON of unknown vintage into canonical shape.
 * Use this for any externally-sourced JSON (DB rows from before the schema
 * unification, user-pasted JSON in the editor). After migration the result
 * is fed through validateCanonicalWorkflow so failures surface immediately.
 */
export function migrateLegacyWorkflow(raw: unknown): Workflow {
  if (!isRecord(raw)) throw new WorkflowSchemaError("expected object", "workflow");
  const nodes = Array.isArray(raw.nodes)
    ? raw.nodes.map((n, i) => migrateLegacyNode(n, `workflow.nodes[${i}]`))
    : [];
  const edges = Array.isArray(raw.edges)
    ? raw.edges.map((e, i) => migrateLegacyEdge(e, `workflow.edges[${i}]`))
    : [];
  const workflow: Workflow = {
    id: optionalString(raw.id) ?? `wf_${Date.now()}`,
    name: typeof raw.name === "string" ? raw.name : "Untitled Workflow",
    nodes,
    edges,
  };
  if (typeof raw.createdAt === "string") workflow.createdAt = raw.createdAt;
  if (typeof raw.updatedAt === "string") workflow.updatedAt = raw.updatedAt;
  return validateCanonicalWorkflow(workflow);
}

// ---------- Vue Flow <-> canonical (internal adapters) ----------

/**
 * Convert a Vue Flow Node into a canonical node. Vue Flow uses `type` for
 * what we call `kind`, and stows everything else inside `data`. Action,
 * settings, sessionId and child arrays are lifted out of `data` here.
 */
function vueNodeToCanonical(node: Node): CanonicalWorkflowNode {
  const sourceData = isRecord(node.data) ? { ...node.data } : {};
  const data: UnknownRecord = { ...sourceData };
  delete data.action;
  delete data.settings;
  delete data.runtime;
  delete data.sessionId;

  const action = optionalString(sourceData.action);

  const settingsRaw = isRecord(sourceData.settings) ? sourceData.settings : undefined;
  const settings: WorkflowNodeSettings | undefined = settingsRaw ? { ...settingsRaw } : undefined;

  const runtimeRaw = isRecord(sourceData.runtime) ? sourceData.runtime : undefined;
  const runtime: WorkflowNodeRuntime = runtimeRaw ? { ...runtimeRaw } : {};
  const sessionId = optionalString(sourceData.sessionId);
  if (sessionId) runtime.sessionId = sessionId;

  const kind: WorkflowNodeKind = isNodeKind(node.type) ? node.type : "action";

  const out: CanonicalWorkflowNode = {
    id: node.id,
    kind,
    position: node.position,
    data,
  };
  if (action) out.action = action;
  if (settings && Object.keys(settings).length) out.settings = settings;
  if (Object.keys(runtime).length) out.runtime = runtime;
  const maybeSelected = (node as unknown as { selected?: unknown }).selected;
  if (typeof maybeSelected === "boolean") out.selected = maybeSelected;
  return out;
}

function canonicalNodeToVue(node: CanonicalWorkflowNode): Node {
  const data: UnknownRecord = { ...node.data };
  if (node.action) data.action = node.action;
  if (node.runtime?.sessionId) data.sessionId = node.runtime.sessionId;
  if (node.settings && Object.keys(node.settings).length) data.settings = { ...node.settings };
  return {
    id: node.id,
    type: node.kind,
    position: node.position,
    data,
  };
}

function vueEdgeToCanonical(edge: Edge): CanonicalWorkflowEdge {
  const out: CanonicalWorkflowEdge = {
    id: edge.id,
    source: edge.source,
    target: edge.target,
  };
  if (edge.sourceHandle !== undefined) out.sourceHandle = edge.sourceHandle;
  if (edge.targetHandle !== undefined) out.targetHandle = edge.targetHandle;
  if (typeof edge.label === "string") out.label = edge.label;
  return out;
}

function canonicalEdgeToVue(edge: CanonicalWorkflowEdge): Edge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    label: edge.label,
  };
}

// ---------- Public store-facing helpers ----------

export function toCanonicalWorkflow(input: {
  id: string;
  name?: string;
  nodes?: Node[];
  edges?: Edge[];
}): Workflow {
  const workflow: Workflow = {
    id: input.id,
    name: input.name || "Untitled Workflow",
    nodes: (input.nodes || []).map(vueNodeToCanonical),
    edges: (input.edges || []).map(vueEdgeToCanonical),
  };
  return validateCanonicalWorkflow(workflow);
}

/**
 * Accept a list of nodes that are EITHER canonical or legacy and produce
 * Vue Flow nodes. Legacy shapes are migrated through migrateLegacyWorkflow
 * so the boundary is explicit.
 */
export function canonicalNodesToVueNodes(nodes: unknown[] | undefined): Node[] {
  if (!nodes || nodes.length === 0) return [];
  const migrated = migrateLegacyWorkflow({ id: `wf_tmp_${Date.now()}`, nodes, edges: [] });
  return migrated.nodes.map(canonicalNodeToVue);
}

export function canonicalEdgesToVueEdges(edges: unknown[] | undefined): Edge[] {
  if (!edges || edges.length === 0) return [];
  const migrated = migrateLegacyWorkflow({ id: `wf_tmp_${Date.now()}`, nodes: [], edges });
  return migrated.edges.map(canonicalEdgeToVue);
}
