import { describe, expect, it } from 'vitest';

import { DAY_MS, FRESH, gapDays, isDue, schedule } from './sm2';

const T0 = 1_700_000_000_000;

describe('sm2 lite', () => {
  it('first Good rating schedules one day out', () => {
    const s = schedule(null, 2, T0);
    expect(s.n).toBe(1);
    expect(s.ease).toBe(2.5);
    expect(s.dueAt).toBe(T0 + 1 * DAY_MS);
    expect(s.rightCount).toBe(1);
    expect(s.lastQuality).toBe(2);
  });

  it('second rating schedules three days out, third by ease', () => {
    const a = schedule(null, 2, T0);
    const b = schedule(a, 2, T0);
    expect(b.dueAt).toBe(T0 + 3 * DAY_MS);
    const c = schedule(b, 2, T0);
    expect(c.dueAt).toBe(T0 + Math.round(2 * 2.5 * 1.6) * DAY_MS);
  });

  it('Again resets the streak, lowers ease and is due now', () => {
    const a = schedule(schedule(null, 3, T0), 3, T0);
    const again = schedule(a, 0, T0);
    expect(again.n).toBe(0);
    expect(again.ease).toBeCloseTo(a.ease - 0.2);
    expect(again.dueAt).toBe(T0);
    expect(again.wrongCount).toBe(1);
  });

  it('clamps ease between 1.3 and 2.8', () => {
    let s = FRESH;
    for (let i = 0; i < 10; i += 1) s = schedule(s, 3, T0);
    expect(s.ease).toBe(2.8);
    for (let i = 0; i < 20; i += 1) s = schedule(s, 0, T0);
    expect(s.ease).toBeCloseTo(1.3);
  });

  it('Hard nudges ease down, Easy nudges it up', () => {
    expect(schedule(null, 1, T0).ease).toBeCloseTo(2.35);
    expect(schedule(null, 3, T0).ease).toBeCloseTo(2.65);
  });

  it('gap table matches the original page', () => {
    expect(gapDays(0, 2.5)).toBe(0);
    expect(gapDays(1, 2.5)).toBe(1);
    expect(gapDays(2, 2.5)).toBe(3);
    expect(gapDays(3, 2.5)).toBe(8);
  });

  it('unseen and overdue questions are due', () => {
    expect(isDue(undefined, T0)).toBe(true);
    expect(isDue({ ...FRESH, dueAt: T0 - 1 }, T0)).toBe(true);
    expect(isDue({ ...FRESH, dueAt: T0 + 1 }, T0)).toBe(false);
  });
});
