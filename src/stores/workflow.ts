import { defineStore } from "pinia";
import { ref, shallowRef, computed } from "vue";
import type { Node, Edge } from "@vue-flow/core";
import type { RecordedNode } from "./browser";

interface Snapshot {
  nodes: Node[];
  edges: Edge[];
}

export const useWorkflowStore = defineStore("workflow", () => {
  const id = ref<string | null>(null);
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
    id.value = null;
    name.value = "Untitled Workflow";
    nodes.value = [];
    edges.value = [];
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
    return {
      id: id.value,
      name: name.value,
      nodes: nodes.value.map((n) => ({
        id: n.id,
        type: n.type || "action",
        position: n.position,
        data: n.data,
      })),
      edges: edges.value.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
        label: typeof e.label === 'string' ? e.label : undefined,
      })),
    };
  }

  function fromJSON(data: { name?: string; nodes?: Array<{ id: string; type?: string; position?: { x: number; y: number }; data?: Record<string, unknown> }>; edges?: Array<{ id: string; source?: string; target?: string; sourceHandle?: string | null; targetHandle?: string | null; label?: string }> }) {
    if (data.name) name.value = data.name;
    if (data.nodes) {
      nodes.value = data.nodes.map((n) => ({
        id: n.id,
        type: n.type || "action",
        position: n.position || { x: 0, y: 0 },
        data: n.data || {},
      }));
    }
    if (data.edges) {
      edges.value = data.edges.map((e) => ({
        id: e.id,
        source: e.source || '',
        target: e.target || '',
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
        label: e.label,
      }));
    }
  }

  return {
    id, name, nodes, edges,
    selectedNodeId, selectedNode, selectNode, updateNodeData,
    addNode, removeNode, clear, importRecordedNodes, toJSON, fromJSON,
    undo, redo, canUndo, canRedo, pushSnapshot,
  };
});
