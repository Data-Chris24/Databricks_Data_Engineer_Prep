import { describe, expect, it } from 'vitest';

import { applyCompletion, blankProgress } from './completion';

const IDS = ['X-S1', 'X-S2', 'X-S3'];
const read = (id: string) => ({ ...blankProgress(id, '2026-09-15T10:00:00Z'), visited: true, read: true, scrollPct: 100 });

describe('applyCompletion', () => {
  it('does not complete a section that was only read to the end', () => {
    const r = applyCompletion({ 'X-S1': read('X-S1') }, {}, IDS);
    expect(r.sections['X-S1'].completed).toBe(false);
    expect(r.sections['X-S1'].read).toBe(true);
    expect(r.completed).toBe(0);
    expect(r.percentComplete).toBe(0);
  });
  it('completes a section whose assignment passed, with the pass time', () => {
    const r = applyCompletion({ 'X-S1': read('X-S1') }, { 'X-S1': '2026-09-15T11:00:00Z' }, IDS);
    expect(r.sections['X-S1']).toMatchObject({ completed: true, completedAt: '2026-09-15T11:00:00Z', read: true });
    expect(r.percentComplete).toBe(33);
  });
  it('synthesises a row for a pass with no progress row, and drops passes outside the exam', () => {
    const r = applyCompletion({}, { 'X-S2': '2026-09-15T11:00:00Z', 'OTHER-S9': '2026-09-15T11:00:00Z' }, IDS);
    expect(Object.keys(r.sections)).toEqual(['X-S2']);
    expect(r.sections['X-S2'].completed).toBe(true);
    expect(r.completed).toBe(1);
  });
  it('takes completion away once the passing run is gone (a reset)', () => {
    const before = applyCompletion({ 'X-S1': read('X-S1') }, { 'X-S1': '2026-09-15T11:00:00Z' }, IDS);
    const after = applyCompletion(before.sections, {}, IDS);
    expect(after.sections['X-S1'].completed).toBe(false);
    expect(after.sections['X-S1'].completedAt).toBeNull();
  });
});
