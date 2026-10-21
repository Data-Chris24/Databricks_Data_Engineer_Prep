import { describe, expect, it } from 'vitest';

import { questions } from './content';
import { attemptOrders, hasNearMisses, keyForLabel, labelFor, optionSet, optionText, shuffledOrder } from './optionOrder';

const bank = questions.filter((q) => q.exam === 'associate');

describe('shuffledOrder', () => {
  it('is a permutation of the options, stable for a seed', () => {
    const q = bank[0];
    const order = shuffledOrder(q, 'seed-1');
    expect([...order].sort()).toEqual(Object.keys(q.options).sort());
    expect(shuffledOrder(q, 'seed-1')).toEqual(order);
  });

  it('moves the right answer around across seeds', () => {
    const q = bank[0];
    const places = new Set(Array.from({ length: 40 }, (_, i) => shuffledOrder(q, `s${i}`).indexOf(q.correct)));
    expect(places.size).toBe(4);
  });
});

describe('attemptOrders', () => {
  const test = bank.slice(0, 45);

  it('spreads the right answer evenly over A-D within a test', () => {
    const orders = attemptOrders(test, 'attempt-123');
    const counts = [0, 0, 0, 0];
    for (const q of test) counts[orders[q.id].indexOf(q.correct)] += 1;
    // 45 questions: 12, 11, 11, 11 in some order.
    expect(Math.max(...counts) - Math.min(...counts)).toBeLessThanOrEqual(1);
  });

  it('gives the review the same order the test showed', () => {
    expect(attemptOrders(test, 'attempt-123')).toEqual(attemptOrders(test, 'attempt-123'));
    expect(attemptOrders(test, 'attempt-123')).not.toEqual(attemptOrders(test, 'attempt-456'));
  });

  it('keeps every option exactly once', () => {
    const orders = attemptOrders(test, 'x');
    for (const q of test) expect([...orders[q.id]].sort()).toEqual(Object.keys(q.options).sort());
  });
});

describe('labels', () => {
  it('maps a stored key to its shown letter and back', () => {
    const order = ['C', 'A', 'D', 'B'] as const;
    expect(labelFor([...order], 'A')).toBe('B');
    expect(keyForLabel([...order], 'B')).toBe('A');
    expect(keyForLabel([...order], 'E')).toBeNull();
  });
});

describe('levels', () => {
  const base = bank[0];
  const q = {
    ...base,
    near: { N1: 'near one', N2: 'near two', N3: 'near three' },
    why: { ...base.why, N1: 'w1', N2: 'w2', N3: 'w3' },
  };
  const wrongAuthored: string[] = Object.keys(q.options).filter((k) => k !== q.correct);
  let n = 0;
  const random = () => ((n = (n * 9301 + 49297) % 233280) / 233280);

  it('standard shows the question as authored', () => {
    expect([...optionSet(q, 'standard', random)].sort()).toEqual(Object.keys(q.options).sort());
  });

  it('medium shows the answer, one near miss and two authored wrong options', () => {
    for (let i = 0; i < 20; i++) {
      const set = optionSet(q, 'medium', random);
      expect(set).toHaveLength(4);
      expect(set).toContain(q.correct);
      expect(set.filter((k) => k.startsWith('N'))).toHaveLength(1);
      expect(set.filter((k) => wrongAuthored.includes(k))).toHaveLength(2);
    }
  });

  it('hard shows the answer and only near misses', () => {
    expect([...optionSet(q, 'hard', random)].sort()).toEqual([q.correct, 'N1', 'N2', 'N3'].sort());
  });

  it('a question without all three near misses stays as authored at every level', () => {
    const partial = { ...base, near: { N1: 'only one' } };
    for (const level of ['medium', 'hard'] as const) {
      expect([...optionSet(partial, level, random)].sort()).toEqual(Object.keys(base.options).sort());
    }
    expect(hasNearMisses(partial)).toBe(false);
    expect(hasNearMisses(q)).toBe(true);
  });

  it('a hard test still spreads the answer over A-D and reviews identically', () => {
    const test = bank.slice(0, 44).map((b) => ({ ...b, near: q.near }));
    const orders = attemptOrders(test, 'hard-1', 'hard');
    const counts = [0, 0, 0, 0];
    for (const t of test) {
      expect([...orders[t.id]].sort()).toEqual([t.correct, 'N1', 'N2', 'N3'].sort());
      counts[orders[t.id].indexOf(t.correct)] += 1;
    }
    expect(counts).toEqual([11, 11, 11, 11]);
    expect(attemptOrders(test, 'hard-1', 'hard')).toEqual(orders);
  });

  it('finds the text behind any key', () => {
    expect(optionText(q, 'N2')).toBe('near two');
    expect(optionText(q, q.correct)).toBe(q.options[q.correct]);
  });
});
