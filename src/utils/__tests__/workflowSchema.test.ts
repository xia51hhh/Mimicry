import { describe, expect, it, vi } from 'vitest';
import {
  WorkflowSchemaError,
  canonicalNodeToVue,
  migrateLegacyWorkflow,
  toCanonicalWorkflow,
  validateCanonicalEdge,
  validateCanonicalNode,
  validateCanonicalWorkflow,
} from '../workflowSchema';

describe('validateCanonicalNode', () => {
  it('accepts a minimal canonical node', () => {
    const node = {
      id: 'n1',
      kind: 'action',
      position: { x: 0, y: 0 },
      data: {},
    };
    expect(validateCanonicalNode(node)).toBe(node);
  });

  it('rejects unknown top-level fields', () => {
    expect(() =>
      validateCanonicalNode({
        id: 'n1',
        kind: 'action',
        position: { x: 0, y: 0 },
        data: {},
        selector: '#legacy',
      }),
    ).toThrow(WorkflowSchemaError);
  });

  it('rejects unknown kind', () => {
    expect(() =>
      validateCanonicalNode({
        id: 'n1',
        kind: 'wormhole',
        position: { x: 0, y: 0 },
        data: {},
      }),
    ).toThrow(/invalid kind/);
  });

  it('requires data to be an object', () => {
    expect(() =>
      validateCanonicalNode({
        id: 'n1',
        kind: 'action',
        position: { x: 0, y: 0 },
        data: 'oops',
      }),
    ).toThrow(/data must be an object/);
  });

  it('requires non-empty id', () => {
    expect(() =>
      validateCanonicalNode({
        id: '',
        kind: 'action',
        position: { x: 0, y: 0 },
        data: {},
      }),
    ).toThrow(/missing or empty id/);
  });
});

describe('validateCanonicalEdge', () => {
  it('accepts minimal canonical edge', () => {
    expect(() => validateCanonicalEdge({ id: 'e1', source: 'a', target: 'b' })).not.toThrow();
  });

  it('rejects edge missing source/target', () => {
    expect(() => validateCanonicalEdge({ id: 'e1' })).toThrow(/source.*target/);
  });

  it('rejects edge fields outside the allowlist', () => {
    expect(() =>
      validateCanonicalEdge({ id: 'e', source: 'a', target: 'b', futureNew: 1 }),
    ).toThrow(/unknown field/);
  });
});

describe('validateCanonicalWorkflow', () => {
  it('requires id, name, nodes[], edges[]', () => {
    expect(() => validateCanonicalWorkflow({})).toThrow();
    expect(() =>
      validateCanonicalWorkflow({ id: 'wf_1', name: 'x', nodes: {}, edges: [] }),
    ).toThrow(/nodes must be an array/);
  });

  it('rejects unknown top-level fields', () => {
    expect(() =>
      validateCanonicalWorkflow({
        id: 'wf_1',
        name: 'x',
        nodes: [],
        edges: [],
        version: 'v2',
      }),
    ).toThrow(/unknown field/);
  });
});

describe('migrateLegacyWorkflow', () => {
  it('lifts legacy flat node params into data', () => {
    const wf = migrateLegacyWorkflow({
      id: 'wf_1',
      name: 'n',
      nodes: [
        {
          id: 'n1',
          type: 'action',
          action: 'Click',
          position: { x: 0, y: 0 },
          selector: '#legacy',
          value: 'hi',
        },
      ],
      edges: [],
    });
    expect(wf.nodes[0]).toMatchObject({
      id: 'n1',
      kind: 'action',
      action: 'Click',
      data: { selector: '#legacy', value: 'hi' },
    });
    expect((wf.nodes[0] as unknown as Record<string, unknown>).selector).toBeUndefined();
  });

  it('collapses session id from any of 5 legacy locations into runtime.sessionId', () => {
    const variants = [
      { sessionId: 's-1' },
      { session_id: 's-2' },
      { data: { sessionId: 's-3' } },
      { data: { session_id: 's-4' } },
      { runtime: { sessionId: 's-5' } },
    ];
    const expected = ['s-1', 's-2', 's-3', 's-4', 's-5'];
    variants.forEach((extras, i) => {
      const wf = migrateLegacyWorkflow({
        id: 'wf',
        name: 'n',
        nodes: [{ id: `n${i}`, type: 'action', position: { x: 0, y: 0 }, ...extras }],
        edges: [],
      });
      expect(wf.nodes[0].runtime?.sessionId).toBe(expected[i]);
    });
  });

  it('hoists settings and action from data when only present there (Vue Flow path)', () => {
    const wf = migrateLegacyWorkflow({
      id: 'wf',
      name: 'n',
      nodes: [
        {
          id: 'n1',
          type: 'action',
          position: { x: 0, y: 0 },
          data: { action: 'Click', selector: '#x', settings: { onError: 'stop' } },
        },
      ],
      edges: [],
    });
    expect(wf.nodes[0].action).toBe('Click');
    expect(wf.nodes[0].settings).toEqual({ onError: 'stop' });
    expect(wf.nodes[0].data).toEqual({ selector: '#x' });
  });

  it('recursively migrates children and elseChildren whether at top level or inside data', () => {
    const wf = migrateLegacyWorkflow({
      id: 'wf',
      name: 'n',
      nodes: [
        {
          id: 'cond',
          type: 'condition',
          condition: "exists('#x')",
          position: { x: 0, y: 0 },
          children: [
            { id: 'c1', type: 'action', action: 'Click', selector: '#a', position: { x: 0, y: 0 } },
          ],
          data: {
            elseChildren: [
              {
                id: 'c2',
                type: 'action',
                action: 'Click',
                selector: '#b',
                position: { x: 0, y: 0 },
              },
            ],
          },
        },
      ],
      edges: [],
    });
    const data = wf.nodes[0].data as Record<string, unknown>;
    expect(Array.isArray(data.children)).toBe(true);
    expect(Array.isArray(data.elseChildren)).toBe(true);
    expect(data.condition).toBe("exists('#x')");
  });

  it('returns the same shape that validateCanonicalWorkflow accepts (round-trip)', () => {
    const migrated = migrateLegacyWorkflow({
      id: 'wf',
      name: 'n',
      nodes: [
        {
          id: 'n1',
          type: 'action',
          action: 'Navigate',
          position: { x: 0, y: 0 },
          url: 'https://x',
        },
      ],
      edges: [],
    });
    expect(() => validateCanonicalWorkflow(migrated)).not.toThrow();
  });
});

describe('toCanonicalWorkflow (store export)', () => {
  it('produces canonical JSON from Vue Flow nodes/edges', () => {
    const wf = toCanonicalWorkflow({
      id: 'wf_x',
      name: 'demo',
      nodes: [
        {
          id: 'n1',
          type: 'action',
          position: { x: 1, y: 2 },
          data: { action: 'Click', selector: '#go', sessionId: 'p1' },
        },
      ],
      edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
    });
    expect(wf.id).toBe('wf_x');
    expect(wf.nodes[0].kind).toBe('action');
    expect(wf.nodes[0].action).toBe('Click');
    expect(wf.nodes[0].data).toEqual({ selector: '#go' });
    expect(wf.nodes[0].runtime?.sessionId).toBe('p1');
  });

  it('validates output and throws on unknown id', () => {
    expect(() =>
      toCanonicalWorkflow({ id: '', name: 'x', nodes: [], edges: [] } as never),
    ).toThrow();
  });
});

describe('migrate + canonicalNodeToVue (store import path)', () => {
  it('accepts both canonical and legacy nodes in the same import', () => {
    const wf = migrateLegacyWorkflow({
      id: 'wf',
      name: 'n',
      nodes: [
        {
          id: 'n1',
          kind: 'action',
          action: 'Click',
          position: { x: 0, y: 0 },
          data: { selector: '#a' },
        },
        {
          id: 'n2',
          type: 'action',
          action: 'Type',
          position: { x: 0, y: 0 },
          selector: '#b',
          value: 'hi',
        },
      ],
      edges: [],
    });
    const vue = wf.nodes.map(canonicalNodeToVue);
    expect(vue).toHaveLength(2);
    expect(vue[0].type).toBe('action');
    expect(vue[0].data).toMatchObject({ action: 'Click', selector: '#a' });
    expect(vue[1].data).toMatchObject({ action: 'Type', selector: '#b', value: 'hi' });
  });
});

describe('edge migration', () => {
  it('preserves Vue Flow rendering metadata round-trip', () => {
    const wf = migrateLegacyWorkflow({
      id: 'wf',
      name: 'n',
      nodes: [],
      edges: [
        {
          id: 'e1',
          source: 'a',
          target: 'b',
          markerEnd: { type: 'arrowclosed' },
          animated: true,
          style: { stroke: '#888' },
        },
      ],
    });
    const e = wf.edges[0] as unknown as Record<string, unknown>;
    expect(e.markerEnd).toEqual({ type: 'arrowclosed' });
    expect(e.animated).toBe(true);
    expect(e.style).toEqual({ stroke: '#888' });
  });

  it('synthesises a deterministic id when source/target known but id missing', () => {
    const wf = migrateLegacyWorkflow({
      id: 'wf',
      name: 'n',
      nodes: [],
      edges: [{ source: 'a', target: 'b' }],
    });
    expect(wf.edges[0].id).toBe('edge_a__b');
  });
});

describe('conflict warnings', () => {
  it('warns when canonical and legacy locations both supply action', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      migrateLegacyWorkflow({
        id: 'wf',
        name: 'n',
        nodes: [
          {
            id: 'n1',
            type: 'action',
            action: 'Click',
            position: { x: 0, y: 0 },
            data: { action: 'Type' },
          },
        ],
        edges: [],
      });
      expect(spy).toHaveBeenCalled();
      const msg = spy.mock.calls.map((c) => c.join(' ')).join('\n');
      expect(msg).toMatch(/action/);
    } finally {
      spy.mockRestore();
    }
  });

  it('warns and keeps data value when legacy top-level duplicates a data param', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      const wf = migrateLegacyWorkflow({
        id: 'wf',
        name: 'n',
        nodes: [
          {
            id: 'n1',
            kind: 'action',
            position: { x: 0, y: 0 },
            data: { selector: '#right' },
            selector: '#WRONG',
          } as never,
          // ^ note: top-level legacy `selector` while data already has it
        ],
        edges: [],
      });
      expect((wf.nodes[0].data as Record<string, unknown>).selector).toBe('#right');
      expect(spy).toHaveBeenCalled();
    } finally {
      spy.mockRestore();
    }
  });
});
