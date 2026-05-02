import { describe, expect, it, vi, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

// Mock Tauri invoke
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(() => Promise.resolve({})),
}));

// Mock vue-flow
vi.mock('@vue-flow/core', () => ({
  useVueFlow: vi.fn(() => ({
    fitView: vi.fn(),
  })),
}));

// Mock action-map (toFrontend is identity in tests)
vi.mock('../../types/action-map', () => ({
  toFrontend: (v: string) => v,
}));

// Mock workflowSchema
vi.mock('../../utils/workflowSchema', () => ({
  canonicalNodeToVue: vi.fn(),
  canonicalEdgeToVue: vi.fn(),
  migrateLegacyWorkflow: vi.fn(),
  toCanonicalWorkflow: vi.fn(),
}));

// Mock dagre
vi.mock('@dagrejs/dagre', () => ({
  default: { graphlib: { Graph: vi.fn() } },
}));

import { useWorkflowStore } from '../workflow';

describe('useWorkflowStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  describe('importRecordedNodes', () => {
    it('places nodes in serpentine layout with 5 per row', () => {
      const store = useWorkflowStore();
      const recorded = Array.from({ length: 12 }, (_, i) => ({
        kind: 'action' as const,
        action: `act_${i}`,
        data: {},
      }));

      store.importRecordedNodes(recorded);

      expect(store.nodes).toHaveLength(12);
      expect(store.edges).toHaveLength(11); // 12 nodes → 11 edges

      // Row 0 (indices 0-4): L→R, all same y
      const row0 = store.nodes.slice(0, 5);
      const y0 = row0[0].position.y;
      expect(row0.every((n) => n.position.y === y0)).toBe(true);
      expect(row0[0].position.x).toBeLessThan(row0[4].position.x);

      // Row 1 (indices 5-9): R→L, same y, different from row 0
      const row1 = store.nodes.slice(5, 10);
      const y1 = row1[0].position.y;
      expect(y1).toBeGreaterThan(y0);
      expect(row1.every((n) => n.position.y === y1)).toBe(true);
      // First node of row 1 (index 5) should be at the RIGHT side
      expect(row1[0].position.x).toBeGreaterThan(row1[4].position.x);

      // Row 2 (indices 10-11): L→R again
      const row2 = store.nodes.slice(10, 12);
      const y2 = row2[0].position.y;
      expect(y2).toBeGreaterThan(y1);
      expect(row2[0].position.x).toBeLessThan(row2[1].position.x);
    });

    it('creates sequential edges between all recorded nodes', () => {
      const store = useWorkflowStore();
      const recorded = [
        { kind: 'action' as const, action: 'click', data: {} },
        { kind: 'action' as const, action: 'type', data: {} },
        { kind: 'action' as const, action: 'wait', data: {} },
      ];

      store.importRecordedNodes(recorded);

      expect(store.edges).toHaveLength(2);
      expect(store.edges[0].source).toBe(store.nodes[0].id);
      expect(store.edges[0].target).toBe(store.nodes[1].id);
      expect(store.edges[1].source).toBe(store.nodes[1].id);
      expect(store.edges[1].target).toBe(store.nodes[2].id);
    });

    it('appends after existing nodes and connects to last', () => {
      const store = useWorkflowStore();
      store.nodes = [{ id: 'existing_1', type: 'action', position: { x: 0, y: 50 }, data: {} }];
      store.edges = [];

      store.importRecordedNodes([{ kind: 'action', action: 'click', data: {} }]);

      expect(store.nodes).toHaveLength(2);
      expect(store.edges).toHaveLength(1);
      expect(store.edges[0].source).toBe('existing_1');
      expect(store.edges[0].target).toBe(store.nodes[1].id);
    });

    it('maps node kinds correctly', () => {
      const store = useWorkflowStore();
      store.importRecordedNodes([
        { kind: 'action', action: 'click', data: {} },
        { kind: 'condition', action: 'if', data: {} },
        { kind: 'loop', action: 'for', data: {} },
      ]);

      expect(store.nodes[0].type).toBe('action');
      expect(store.nodes[1].type).toBe('condition');
      expect(store.nodes[2].type).toBe('loop');
    });
  });

  describe('undo/redo', () => {
    it('undo restores previous state', () => {
      const store = useWorkflowStore();
      store.nodes = [{ id: 'n1', type: 'action', position: { x: 0, y: 0 }, data: {} }];
      store.pushSnapshot();
      store.nodes = [
        { id: 'n1', type: 'action', position: { x: 0, y: 0 }, data: {} },
        { id: 'n2', type: 'action', position: { x: 100, y: 0 }, data: {} },
      ];

      store.undo();

      expect(store.nodes).toHaveLength(1);
      expect(store.nodes[0].id).toBe('n1');
    });

    it('redo restores after undo', () => {
      const store = useWorkflowStore();
      store.pushSnapshot();
      store.nodes = [{ id: 'n1', type: 'action', position: { x: 0, y: 0 }, data: {} }];
      store.pushSnapshot();
      store.undo();
      store.redo();

      expect(store.nodes).toHaveLength(1);
    });
  });
});
