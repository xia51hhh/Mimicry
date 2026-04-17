import { defineStore } from "pinia";
import { ref, shallowRef } from "vue";
import type { Node, Edge } from "@vue-flow/core";

export const useWorkflowStore = defineStore("workflow", () => {
  const id = ref<string | null>(null);
  const name = ref("Untitled Workflow");
  const nodes = shallowRef<Node[]>([]);
  const edges = shallowRef<Edge[]>([]);

  function addNode(type: string, position: { x: number; y: number }, data: Record<string, unknown> = {}) {
    const nodeId = `node_${Date.now()}`;
    nodes.value = [...nodes.value, { id: nodeId, type, position, data }];
    return nodeId;
  }

  function removeNode(nodeId: string) {
    nodes.value = nodes.value.filter((n) => n.id !== nodeId);
    edges.value = edges.value.filter((e) => e.source !== nodeId && e.target !== nodeId);
  }

  function clear() {
    id.value = null;
    name.value = "Untitled Workflow";
    nodes.value = [];
    edges.value = [];
  }

  function importRecordedNodes(recordedNodes: any[]) {
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
      name: name.value,
      nodes: nodes.value.map((n) => ({
        id: n.id,
        type: n.type || "action",
        ...n.data,
      })),
    };
  }

  return { id, name, nodes, edges, addNode, removeNode, clear, importRecordedNodes, toJSON };
});
