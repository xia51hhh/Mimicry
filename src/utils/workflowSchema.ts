import type { Edge, Node } from '@vue-flow/core';
import type {
  CanonicalWorkflowEdge,
  CanonicalWorkflowNode,
  Workflow,
  WorkflowNodeKind,
  WorkflowNodeRuntime,
  WorkflowNodeSettings,
} from '../types/workflow';

type UnknownRecord = Record<string, unknown>;

const NODE_KINDS = new Set<WorkflowNodeKind>(['action', 'condition', 'loop', 'group']);

const ALLOWED_NODE_KEYS = new Set([
  'id',
  'kind',
  'action',
  'position',
  'data',
  'settings',
  'runtime',
  'selected',
]);

// Edge keys we keep on the canonical wire format. The first group is
// semantic graph metadata; the second group is Vue Flow rendering metadata
// that round-trips through canvas <-> JSON without affecting execution.
const ALLOWED_EDGE_KEYS = new Set([
  'id',
  'source',
  'target',
  'sourceHandle',
  'targetHandle',
  'label',
  // Vue Flow rendering metadata (preserved as-is).
  'type',
  'animated',
  'style',
  'data',
  'markerEnd',
  'markerStart',
  'selected',
  'zIndex',
  'hidden',
  'deletable',
  'selectable',
  'focusable',
  'interactionWidth',
  'labelStyle',
  'labelShowBg',
  'labelBgStyle',
  'labelBgPadding',
  'labelBgBorderRadius',
  'ariaLabel',
  'updatable',
  'class',
  'events',
]);

const ALLOWED_WORKFLOW_KEYS = new Set(['id', 'name', 'nodes', 'edges', 'createdAt', 'updatedAt']);

export class WorkflowSchemaError extends Error {
  constructor(
    message: string,
    public readonly path: string,
  ) {
    super(`${message} (at ${path})`);
    this.name = 'WorkflowSchemaError';
  }
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function isNodeKind(value: unknown): value is WorkflowNodeKind {
  return typeof value === 'string' && NODE_KINDS.has(value as WorkflowNodeKind);
}

// ---------- Validation ----------
//
// Validation is structural and stops at the `data` payload boundary —
// `data` is documented as an opaque per-action payload (URL/selector/timeout
// for navigate, condition expression for if-blocks, loop config for loops,
// etc.). Each action handler is responsible for reading what it needs out
// of `data`. Validating its inner shape here would force schema-bumping on
// every new action.

export function validateCanonicalNode(raw: unknown, path = 'node'): CanonicalWorkflowNode {
  if (!isRecord(raw)) {
    throw new WorkflowSchemaError('expected object', path);
  }
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_NODE_KEYS.has(key)) {
      throw new WorkflowSchemaError(
        `unknown field "${key}" — canonical nodes only allow ${[...ALLOWED_NODE_KEYS].join(', ')}; legacy fields must be migrated via migrateLegacyWorkflow()`,
        path,
      );
    }
  }
  const id = optionalString(raw.id);
  if (!id) throw new WorkflowSchemaError('missing or empty id', path);
  if (!isNodeKind(raw.kind)) {
    throw new WorkflowSchemaError(`invalid kind ${JSON.stringify(raw.kind)}`, `${path}.kind`);
  }
  if (
    !isRecord(raw.position) ||
    typeof raw.position.x !== 'number' ||
    typeof raw.position.y !== 'number'
  ) {
    throw new WorkflowSchemaError('position must be { x: number, y: number }', `${path}.position`);
  }
  if (!isRecord(raw.data)) {
    throw new WorkflowSchemaError('data must be an object', `${path}.data`);
  }
  if (raw.action !== undefined && typeof raw.action !== 'string') {
    throw new WorkflowSchemaError('action must be a string', `${path}.action`);
  }
  if (raw.settings !== undefined && !isRecord(raw.settings)) {
    throw new WorkflowSchemaError('settings must be an object', `${path}.settings`);
  }
  if (raw.runtime !== undefined && !isRecord(raw.runtime)) {
    throw new WorkflowSchemaError('runtime must be an object', `${path}.runtime`);
  }
  if (raw.selected !== undefined && typeof raw.selected !== 'boolean') {
    throw new WorkflowSchemaError('selected must be boolean', `${path}.selected`);
  }
  return raw as unknown as CanonicalWorkflowNode;
}

export function validateCanonicalEdge(raw: unknown, path = 'edge'): CanonicalWorkflowEdge {
  if (!isRecord(raw)) throw new WorkflowSchemaError('expected object', path);
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_EDGE_KEYS.has(key)) {
      throw new WorkflowSchemaError(
        `unknown field "${key}" — extend ALLOWED_EDGE_KEYS if this is a Vue Flow rendering field that should round-trip`,
        path,
      );
    }
  }
  const id = optionalString(raw.id);
  const source = optionalString(raw.source);
  const target = optionalString(raw.target);
  if (!id || !source || !target) {
    throw new WorkflowSchemaError('edge requires id, source, target', path);
  }
  return raw as unknown as CanonicalWorkflowEdge;
}

export function validateCanonicalWorkflow(raw: unknown): Workflow {
  if (!isRecord(raw)) throw new WorkflowSchemaError('expected object', 'workflow');
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_WORKFLOW_KEYS.has(key)) {
      throw new WorkflowSchemaError(`unknown field "${key}"`, 'workflow');
    }
  }
  if (!optionalString(raw.id)) {
    throw new WorkflowSchemaError('workflow id must be non-empty string', 'workflow.id');
  }
  if (typeof raw.name !== 'string') {
    throw new WorkflowSchemaError('workflow name must be a string', 'workflow.name');
  }
  if (!Array.isArray(raw.nodes)) {
    throw new WorkflowSchemaError('workflow.nodes must be an array', 'workflow.nodes');
  }
  if (!Array.isArray(raw.edges)) {
    throw new WorkflowSchemaError('workflow.edges must be an array', 'workflow.edges');
  }
  raw.nodes.forEach((n, i) => validateCanonicalNode(n, `workflow.nodes[${i}]`));
  raw.edges.forEach((e, i) => validateCanonicalEdge(e, `workflow.edges[${i}]`));
  return raw as unknown as Workflow;
}

// ---------- Legacy migration (explicit, opt-in) ----------

const LEGACY_NODE_TOP_KEYS = new Set([
  ...ALLOWED_NODE_KEYS,
  'type',
  'session_id',
  'sessionId',
  'children',
  'elseChildren',
]);

interface SessionIdSource {
  topSnake?: unknown;
  topCamel?: unknown;
  dataSnake?: unknown;
  dataCamel?: unknown;
  runtime?: unknown;
}

function pickSessionId(src: SessionIdSource): string | undefined {
  return (
    optionalString(src.topCamel) ??
    optionalString(src.topSnake) ??
    optionalString(src.dataCamel) ??
    optionalString(src.dataSnake) ??
    optionalString(src.runtime)
  );
}

function reportConflict(path: string, field: string, kept: unknown, dropped: unknown) {
  if (kept === dropped) return;
  console.warn(
    `[workflowSchema] ${path}.${field}: canonical value ${JSON.stringify(kept)} kept, ` +
      `legacy duplicate ${JSON.stringify(dropped)} ignored`,
  );
}

function migrateLegacyNode(raw: unknown, path: string): CanonicalWorkflowNode {
  if (!isRecord(raw)) {
    throw new WorkflowSchemaError('expected object', path);
  }
  const sourceData = isRecord(raw.data) ? { ...raw.data } : {};

  const kindCandidate = raw.kind ?? raw.type ?? sourceData.kind;
  const kind: WorkflowNodeKind = isNodeKind(kindCandidate) ? kindCandidate : 'action';

  const data: UnknownRecord = { ...sourceData };
  delete data.action;
  delete data.settings;
  delete data.runtime;
  delete data.sessionId;
  delete data.session_id;
  delete data.kind;

  // action: prefer canonical (top-level), warn on conflict.
  const action = optionalString(raw.action) ?? optionalString(sourceData.action);
  if (raw.action !== undefined && sourceData.action !== undefined) {
    reportConflict(path, 'action', raw.action, sourceData.action);
  }

  // settings: prefer canonical, warn on conflict.
  const settingsRaw = isRecord(raw.settings)
    ? raw.settings
    : isRecord(sourceData.settings)
      ? sourceData.settings
      : undefined;
  if (isRecord(raw.settings) && isRecord(sourceData.settings)) {
    reportConflict(path, 'settings', raw.settings, sourceData.settings);
  }
  const settings: WorkflowNodeSettings | undefined = settingsRaw ? { ...settingsRaw } : undefined;

  const runtimeRaw = isRecord(raw.runtime)
    ? raw.runtime
    : isRecord(sourceData.runtime)
      ? sourceData.runtime
      : undefined;
  const runtime: WorkflowNodeRuntime = runtimeRaw ? { ...runtimeRaw } : {};
  const sessionId = pickSessionId({
    topCamel: raw.sessionId,
    topSnake: raw.session_id,
    dataCamel: sourceData.sessionId,
    dataSnake: sourceData.session_id,
    runtime: runtime.sessionId,
  });
  if (sessionId) runtime.sessionId = sessionId;

  // Legacy: top-level extras (selector, url, value, etc.) get tucked into data.
  for (const [key, value] of Object.entries(raw)) {
    if (LEGACY_NODE_TOP_KEYS.has(key)) continue;
    if (key in data) {
      reportConflict(`${path}.data`, key, data[key], value);
      continue;
    }
    data[key] = value;
  }

  // children / elseChildren: move under data, recurse.
  if (Array.isArray(raw.children)) {
    data.children = raw.children.map((c, i) => migrateLegacyNode(c, `${path}.children[${i}]`));
  } else if (Array.isArray(sourceData.children)) {
    data.children = sourceData.children.map((c, i) =>
      migrateLegacyNode(c, `${path}.data.children[${i}]`),
    );
  }
  if (Array.isArray(raw.elseChildren)) {
    data.elseChildren = raw.elseChildren.map((c, i) =>
      migrateLegacyNode(c, `${path}.elseChildren[${i}]`),
    );
  } else if (Array.isArray(sourceData.elseChildren)) {
    data.elseChildren = sourceData.elseChildren.map((c, i) =>
      migrateLegacyNode(c, `${path}.data.elseChildren[${i}]`),
    );
  }

  const node: CanonicalWorkflowNode = {
    id: optionalString(raw.id) ?? `node_${Date.now()}`,
    kind,
    position: isRecord(raw.position)
      ? { x: Number(raw.position.x ?? 0), y: Number(raw.position.y ?? 0) }
      : { x: 0, y: 0 },
    data,
  };
  if (action) node.action = action;
  if (settings && Object.keys(settings).length) node.settings = settings;
  if (Object.keys(runtime).length) node.runtime = runtime;
  if (typeof raw.selected === 'boolean') node.selected = raw.selected;
  return node;
}

function deterministicEdgeId(source: string, target: string): string {
  // Stable across reloads; collisions inside a single workflow get resolved
  // by validateCanonicalWorkflow downstream (duplicate check is a follow-up).
  return `edge_${source}__${target}`;
}

function migrateLegacyEdge(raw: unknown, path: string): CanonicalWorkflowEdge {
  if (!isRecord(raw)) throw new WorkflowSchemaError('expected object', path);
  const source = optionalString(raw.source);
  const target = optionalString(raw.target);
  if (!source || !target) throw new WorkflowSchemaError('edge requires source and target', path);
  const id = optionalString(raw.id) ?? deterministicEdgeId(source, target);

  const edge: CanonicalWorkflowEdge = { id, source, target };
  // Pass through every field validateCanonicalEdge will accept; rejecting
  // unknown fields here would break round-trips of in-memory Vue Flow edges
  // that legitimately carry rendering metadata like `markerEnd`.
  for (const [key, value] of Object.entries(raw)) {
    if (key === 'id' || key === 'source' || key === 'target') continue;
    if (!ALLOWED_EDGE_KEYS.has(key)) continue;
    if (value === undefined) continue;
    (edge as unknown as UnknownRecord)[key] = value;
  }
  return edge;
}

/**
 * Migrate a workflow JSON of unknown vintage into canonical shape and
 * validate the result. Use this for any externally-sourced JSON: DB rows
 * from before the schema unification, recorder output, user-pasted JSON.
 */
export function migrateLegacyWorkflow(raw: unknown): Workflow {
  if (!isRecord(raw)) throw new WorkflowSchemaError('expected object', 'workflow');
  const nodes = Array.isArray(raw.nodes)
    ? raw.nodes.map((n, i) => migrateLegacyNode(n, `workflow.nodes[${i}]`))
    : [];
  const edges = Array.isArray(raw.edges)
    ? raw.edges.map((e, i) => migrateLegacyEdge(e, `workflow.edges[${i}]`))
    : [];
  const workflow: Workflow = {
    id: optionalString(raw.id) ?? `wf_${Date.now()}`,
    name: typeof raw.name === 'string' ? raw.name : 'Untitled Workflow',
    nodes,
    edges,
  };
  if (typeof raw.createdAt === 'string') workflow.createdAt = raw.createdAt;
  if (typeof raw.updatedAt === 'string') workflow.updatedAt = raw.updatedAt;
  return validateCanonicalWorkflow(workflow);
}

// ---------- Vue Flow <-> canonical (exported adapters) ----------

/**
 * Convert a Vue Flow Node into a canonical node. Vue Flow uses `type` for
 * what we call `kind`, and stows action params inside `data`. This function
 * lifts action / settings / sessionId out of `data` into the canonical
 * top-level fields.
 */
export function vueNodeToCanonical(node: Node): CanonicalWorkflowNode {
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

  const kind: WorkflowNodeKind = isNodeKind(node.type) ? node.type : 'action';

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
  if (typeof maybeSelected === 'boolean') out.selected = maybeSelected;
  return out;
}

export function canonicalNodeToVue(node: CanonicalWorkflowNode): Node {
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

export function vueEdgeToCanonical(edge: Edge): CanonicalWorkflowEdge {
  const out: CanonicalWorkflowEdge = {
    id: edge.id,
    source: edge.source,
    target: edge.target,
  };
  // Forward only the Vue Flow rendering fields the canonical edge accepts,
  // skipping `undefined` so the JSON output stays clean.
  for (const [key, value] of Object.entries(edge as unknown as UnknownRecord)) {
    if (key === 'id' || key === 'source' || key === 'target') continue;
    if (!ALLOWED_EDGE_KEYS.has(key)) continue;
    if (value === undefined) continue;
    (out as unknown as UnknownRecord)[key] = value;
  }
  return out;
}

export function canonicalEdgeToVue(edge: CanonicalWorkflowEdge): Edge {
  // Spread the whole canonical edge — every key is in ALLOWED_EDGE_KEYS,
  // so Vue Flow gets exactly the rendering fields the JSON carries, and
  // `undefined` keys are not serialized into the object.
  const out: UnknownRecord = {};
  for (const [key, value] of Object.entries(edge as unknown as UnknownRecord)) {
    if (value === undefined) continue;
    out[key] = value;
  }
  return out as unknown as Edge;
}

// ---------- Public store-facing helpers ----------

export function toCanonicalWorkflow(input: {
  id: string;
  name?: string;
  nodes?: Node[];
  edges?: Edge[];
  createdAt?: string;
  updatedAt?: string;
}): Workflow {
  const workflow: Workflow = {
    id: input.id,
    name: input.name || 'Untitled Workflow',
    nodes: (input.nodes || []).map(vueNodeToCanonical),
    edges: (input.edges || []).map(vueEdgeToCanonical),
  };
  if (input.createdAt) workflow.createdAt = input.createdAt;
  if (input.updatedAt) workflow.updatedAt = input.updatedAt;
  return validateCanonicalWorkflow(workflow);
}
