import { describe, expect, it } from 'vitest';

import { questions } from './content';
import { attemptOrders, keyForLabel, labelFor, shuffledOrder } from './optionOrder';

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
