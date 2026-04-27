import { defineStore } from "pinia";
import { ref, shallowRef, computed } from "vue";
import { invoke } from "@tauri-apps/api/core";
import type { Node, Edge } from "@vue-flow/core";
import type { RecordedNode } from "./browser";
import { errorMessage } from "../types/ipc";
import dagre from "@dagrejs/dagre";
import {
  canonicalEdgeToVue,
  canonicalNodeToVue,
  migrateLegacyWorkflow,
  toCanonicalWorkflow,
} from "../utils/workflowSchema";

interface Snapshot {
  nodes: Node[];
  edges: Edge[];
}

function generateWorkflowId(): string {
  return `wf_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useWorkflowStore = defineStore("workflow", () => {
  const id = ref<string>(generateWorkflowId());
  const persisted = ref(false);
  const name = ref("Untitled Workflow");
  const nodes = shallowRef<Node[]>([]);
  const edges = shallowRef<Edge[]>([]);
  const selectedNodeId = ref<string | null>(null);

  // Undo/Redo stacks
  const undoStack = shallowRef<Snapshot[]>([]);
  const redoStack = shallowRef<Snapshot[]>([]);
  const maxHistory = 50;

  function pushSnapshot() {
    undoStack.value = [...undoStack.value.slice(-maxHistory + 1), {
      nodes: JSON.parse(JSON.stringify(nodes.value)),
      edges: JSON.parse(JSON.stringify(edges.value)),
    }];
    redoStack.value = [];
  }

  function undo() {
    if (undoStack.value.length === 0) return;
    const snapshot = undoStack.value[undoStack.value.length - 1];
    undoStack.value = undoStack.value.slice(0, -1);
    redoStack.value = [...redoStack.value, {
      nodes: JSON.parse(JSON.stringify(nodes.value)),
      edges: JSON.parse(JSON.stringify(edges.value)),
    }];
    nodes.value = snapshot.nodes;
    edges.value = snapshot.edges;
  }

  function redo() {
    if (redoStack.value.length === 0) return;
    const snapshot = redoStack.value[redoStack.value.length - 1];
    redoStack.value = redoStack.value.slice(0, -1);
    undoStack.value = [...undoStack.value, {
      nodes: JSON.parse(JSON.stringify(nodes.value)),
      edges: JSON.parse(JSON.stringify(edges.value)),
    }];
    nodes.value = snapshot.nodes;
    edges.value = snapshot.edges;
  }

  const canUndo = computed(() => undoStack.value.length > 0);
  const canRedo = computed(() => redoStack.value.length > 0);

  const selectedNode = computed(() => {
    if (!selectedNodeId.value) return null;
    return nodes.value.find((n) => n.id === selectedNodeId.value) || null;
  });

  function selectNode(nodeId: string | null) {
    selectedNodeId.value = nodeId;
  }

  function updateNodeData(nodeId: string, data: Record<string, unknown>) {
    nodes.value = nodes.value.map((n) =>
      n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
    );
  }

  function addNode(type: string, position: { x: number; y: number }, data: Record<string, unknown> = {}) {
    pushSnapshot();
    const nodeId = `node_${Date.now()}`;
    nodes.value = [...nodes.value, { id: nodeId, type, position, data }];
    return nodeId;
  }

  function removeNode(nodeId: string) {
    pushSnapshot();
    nodes.value = nodes.value.filter((n) => n.id !== nodeId);
    edges.value = edges.value.filter((e) => e.source !== nodeId && e.target !== nodeId);
  }

  function clear() {
    id.value = generateWorkflowId();
    persisted.value = false;
    name.value = "Untitled Workflow";
    nodes.value = [];
    edges.value = [];
    selectedNodeId.value = null;
  }

  function importRecordedNodes(recordedNodes: RecordedNode[]) {
    const startY = nodes.value.length > 0
      ? Math.max(...nodes.value.map(n => n.position.y)) + 100
      : 50;

    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];
    let prevId: string | null = nodes.value.length > 0 ? nodes.value[nodes.value.length - 1].id : null;

    recordedNodes.forEach((rn, i) => {
      const nodeId = `rec_${Date.now()}_${i}`;
      const nodeType = rn.type === "condition" ? "condition" : rn.type === "loop" ? "loop" : "action";
      newNodes.push({
        id: nodeId,
        type: nodeType,
        position: { x: 300, y: startY + i * 80 },
        data: { label: `${rn.action || rn.type}`, ...rn },
      });
      if (prevId) {
        newEdges.push({
          id: `edge_${prevId}_${nodeId}`,
          source: prevId,
          target: nodeId,
        });
      }
      prevId = nodeId;
    });

    nodes.value = [...nodes.value, ...newNodes];
    edges.value = [...edges.value, ...newEdges];
  }

  function toJSON() {
    return toCanonicalWorkflow({
      id: id.value,
      name: name.value,
      nodes: nodes.value,
      edges: edges.value,
    });
  }

  function fromJSON(data: { id?: string; name?: string; nodes?: unknown[]; edges?: unknown[] }) {
    // Run the full record through migrateLegacyWorkflow so the validator
    // sees workflow-level fields (id/name) and gives precise error paths.
    const canonical = migrateLegacyWorkflow({
      id: data.id ?? id.value,
      name: data.name ?? name.value,
      nodes: data.nodes ?? [],
      edges: data.edges ?? [],
    });
    if (data.id) id.value = canonical.id;
    if (data.name) name.value = canonical.name;
    if (data.nodes) nodes.value = canonical.nodes.map(canonicalNodeToVue);
    if (data.edges) edges.value = canonical.edges.map(canonicalEdgeToVue);
  }

  // --- Persistence (Tauri invoke) ---

  interface WorkflowRecord {
    id: string;
    name: string;
    nodes: unknown[];
    edges: unknown[];
    createdAt: string;
    updatedAt: string;
  }

  const workflowList = shallowRef<WorkflowRecord[]>([]);
  const loading = ref(false);

  async function fetchList() {
    loading.value = true;
    try {
      workflowList.value = await invoke<WorkflowRecord[]>("workflow_list");
    } finally {
      loading.value = false;
    }
  }

  async function loadWorkflow(workflowId: string) {
    const record = await invoke<WorkflowRecord | null>("workflow_get", { id: workflowId });
    if (record) {
      fromJSON({
        id: record.id,
        name: record.name,
        nodes: record.nodes as never[],
        edges: record.edges as never[],
      });
      persisted.value = true;
    }
  }

  async function createWorkflow(workflowName: string = "Untitled Workflow") {
    const record = await invoke<WorkflowRecord>("workflow_create", { name: workflowName });
    id.value = record.id;
    name.value = record.name;
    nodes.value = [];
    edges.value = [];
    persisted.value = true;
    await fetchList();
  }

  async function saveWorkflow() {
    if (!persisted.value) return;
    const data = toJSON();
    const now = new Date().toISOString();
    await invoke("workflow_save", {
      workflow: {
        id: data.id,
        name: data.name,
        nodes: data.nodes,
        edges: data.edges,
        createdAt: now,
        updatedAt: now,
      },
    });
    await fetchList();
  }

  async function deleteWorkflow(workflowId: string) {
    await invoke("workflow_delete", { id: workflowId });
    if (id.value === workflowId) {
      clear();
    }
    await fetchList();
  }

  const jsonText = computed(() => JSON.stringify(toJSON(), null, 2));

  function applyJsonText(text: string): { success: boolean; error?: string } {
    try {
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== "object") {
        return { success: false, error: "Workflow JSON must be an object" };
      }
      const canonical = migrateLegacyWorkflow({
        id: parsed.id ?? id.value,
        name: parsed.name ?? name.value,
        nodes: Array.isArray(parsed.nodes) ? parsed.nodes : [],
        edges: Array.isArray(parsed.edges) ? parsed.edges : [],
      });

      const existingPositions = new Map(
        nodes.value.map((n) => [n.id, n.position])
      );

      const newNodes = canonical.nodes.map(canonicalNodeToVue).map((node) => ({
        ...node,
        position: node.position || existingPositions.get(node.id) || { x: 0, y: 0 },
      }));
      const newEdges = canonical.edges.map(canonicalEdgeToVue);

      pushSnapshot();
      nodes.value = newNodes;
      edges.value = newEdges;
      if (parsed.name) name.value = canonical.name;

      return { success: true };
    } catch (e) {
      return { success: false, error: errorMessage(e) };
    }
  }

  function autoLayout(direction: "TB" | "LR" = "TB") {
    pushSnapshot();
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: direction, nodesep: 50, ranksep: 80 });

    nodes.value.forEach((node) => {
      g.setNode(node.id, { width: 200, height: 60 });
    });
    edges.value.forEach((edge) => {
      g.setEdge(edge.source, edge.target);
    });

    dagre.layout(g);

    nodes.value = nodes.value.map((node) => {
      const pos = g.node(node.id);
      return {
        ...node,
        position: { x: pos.x - 100, y: pos.y - 30 },
      };
    });
  }

  return {
    id, name, nodes, edges, persisted,
    selectedNodeId, selectedNode, selectNode, updateNodeData,
    addNode, removeNode, clear, importRecordedNodes, toJSON, fromJSON,
    undo, redo, canUndo, canRedo, pushSnapshot,
    workflowList, loading, fetchList, loadWorkflow, createWorkflow, saveWorkflow, deleteWorkflow,
    jsonText, applyJsonText, autoLayout,
  };
});
