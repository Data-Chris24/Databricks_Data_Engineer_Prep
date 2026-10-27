import { describe, expect, it } from 'vitest';

import { notebooks } from './content';
import { distance, findStrays, label, matches, pathsToProbe, RAW, statusOf, type UcSnapshot, type UnitResources, unitView } from './units';

const all: Record<string, UnitResources> = {
  'ASSOC-S2': {
    setup: [{ kind: 'folder', name: `${RAW}/s2_teach` }],
    lesson: [
      { kind: 'table', name: 'workspace.de_prep.bronze_orders' },
      { kind: 'table', name: 'workspace.de_prep.al_lesson_*', transient: true },
    ],
    assignment: [{ kind: 'table', name: 'workspace.de_prep.silver_sensor_readings' }],
  },
  'PRO-S4': {
    setup: [
      { kind: 'table', name: 'workspace.de_prep.pro_s4_teach_orders' },
      { kind: 'volume', name: 'workspace.de_prep.pro_s4_assess_files' },
    ],
    lesson: [],
    assignment: [{ kind: 'share', name: 'pro_s4_partner_share' }],
  },
  'PRO-S8': { setup: [{ kind: 'catalog', name: 'pro_s8_teach' }], lesson: [], assignment: [] },
};

function snap(tables: string[], extra: Partial<UcSnapshot> = {}): UcSnapshot {
  return {
    tables: new Set(tables),
    tableSchemas: new Set(['workspace.de_prep', 'workspace.default']),
    functions: new Set(),
    volumes: new Set(),
    catalogs: new Set(),
    shares: null,
    recipients: new Set(),
    connections: new Set(),
    paths: new Set(),
    ...extra,
  };
}

describe('statusOf', () => {
  it('is green only for what the snapshot has, counts patterns, and is unknown where it cannot see', () => {
    const s = snap(['workspace.de_prep.al_lesson_a', 'workspace.de_prep.al_lesson_b'], { paths: new Set([`${RAW}/s2_teach`]) });
    expect(statusOf({ kind: 'folder', name: `${RAW}/s2_teach`, group: 'setup' }, s).exists).toBe(true);
    expect(statusOf({ kind: 'table', name: 'workspace.de_prep.bronze_orders', group: 'lesson' }, s).exists).toBe(false);
    expect(statusOf({ kind: 'table', name: 'workspace.de_prep.al_lesson_*', group: 'lesson' }, s)).toMatchObject({ exists: true, count: 2 });
    expect(statusOf({ kind: 'share', name: 'pro_s4_partner_share', group: 'assignment' }, s).exists).toBeNull();
    expect(statusOf({ kind: 'table', name: 'workspace.de_prep_staging.x', group: 'assignment' }, s).exists).toBeNull();
  });
});

describe('unitView', () => {
  it('is ready when every set-up resource exists, and lists other units still present', () => {
    const s = snap(['workspace.de_prep.pro_s4_teach_orders'], { paths: new Set([`${RAW}/s2_teach`]), catalogs: new Set(['pro_s8_teach']) });
    const v = unitView('ASSOC-S2', all, s);
    expect(v.ready).toBe(true);
    expect(v.others.map((o) => o.unitId)).toEqual(['PRO-S4', 'PRO-S8']);
    expect(v.others[0].resources.map((r) => r.name)).toEqual(['workspace.de_prep.pro_s4_teach_orders']);
    expect(v.quota).toEqual({ used: 1, limit: 100, schema: 'workspace.de_prep' });
  });

  it('is not ready while a set-up resource is missing', () => {
    expect(unitView('ASSOC-S2', all, snap([])).ready).toBe(false);
  });

  it('gates nothing when Unity Catalog cannot be read', () => {
    const v = unitView('ASSOC-S2', all, null);
    expect(v.ready).toBe(true);
    expect(v.resources.every((r) => r.exists === null)).toBe(true);
    expect(v.quota).toBeNull();
  });
});

describe('findStrays', () => {
  it('lists undeclared tables with a near-miss suggestion, never a declared or pattern-matched one', () => {
    const s = snap([
      'workspace.de_prep.bronze_orders',
      'workspace.de_prep.al_lesson_x',
      'workspace.de_prep.bronze_order',
      'workspace.default.books_silver',
    ]);
    expect(findStrays(all, s)).toEqual([
      { name: 'workspace.de_prep.bronze_order', suggestion: 'workspace.de_prep.bronze_orders' },
      { name: 'workspace.default.books_silver', suggestion: null },
    ]);
  });
});

describe('helpers', () => {
  it('distance caps at max + 1', () => {
    expect(distance('silver_orders', 'silver_order')).toBe(1);
    expect(distance('abc', 'xyz')).toBe(3);
    expect(distance('a', 'abcdef')).toBe(3);
  });
  it('matches only a trailing star', () => {
    expect(matches('workspace.de_prep.al_lesson_*', 'workspace.de_prep.AL_LESSON_X')).toBe(true);
    expect(matches('workspace.de_prep.x', 'workspace.de_prep.xy')).toBe(false);
  });
  it('labels resources briefly', () => {
    expect(label({ kind: 'folder', name: `${RAW}/s2_teach` })).toBe('raw/s2_teach/');
    expect(label({ kind: 'table', name: 'workspace.de_prep.bronze_orders' })).toBe('bronze_orders');
    expect(label({ kind: 'table', name: 'workspace.de_prep_staging.s5_channel_summary' })).toBe('workspace.de_prep_staging.s5_channel_summary');
    expect(label({ kind: 'catalog', name: 'pro_s8_teach' })).toBe('catalog pro_s8_teach');
  });
});

describe('the content build', () => {
  it('embeds every section\'s declared resources, with set-up resources to wait for', () => {
    for (const [id, nb] of Object.entries(notebooks)) {
      expect(nb.resources, id).toBeDefined();
      expect(nb.resources.setup.filter((r) => !r.transient).length, id).toBeGreaterThan(0);
    }
    expect(pathsToProbe(Object.fromEntries(Object.entries(notebooks).map(([k, v]) => [k, v.resources])))).toContain(`${RAW}/s2_teach`);
  });
});
