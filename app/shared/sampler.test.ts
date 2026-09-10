import { describe, expect, it } from 'vitest';

import { exams, questions } from './content';
import type { Exam, Question } from './types';
import { apportion, BankTooSmallError, mulberry32, sampleTest } from './sampler';

const associate = exams.find((e) => e.id === 'associate') as Exam;
const professional = exams.find((e) => e.id === 'professional') as Exam;

describe('apportion', () => {
  it('splits the Associate items by weight and sums to the item count', () => {
    const weights = Object.fromEntries(associate.sections.map((s) => [s.id, s.weight]));
    const q = apportion(weights, 45);
    expect(Object.values(q).reduce((a, b) => a + b, 0)).toBe(45);
    // 6/21/22/16/10/10/15 % of 45 -> 2.7/9.45/9.9/7.2/4.5/4.5/6.75, Hamilton rounding:
    expect(q).toEqual({
      'ASSOC-S1': 3,
      'ASSOC-S2': 9,
      'ASSOC-S3': 10,
      'ASSOC-S4': 7,
      'ASSOC-S5': 5,
      'ASSOC-S6': 4,
      'ASSOC-S7': 7,
    });
  });
});

describe('sampleTest', () => {
  it('draws exactly the exam length from the real Associate bank', () => {
    const ids = sampleTest({ exam: associate, bank: questions, seen: new Map(), rng: mulberry32(1) });
    expect(ids).toHaveLength(associate.items);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('refuses the Professional bank while it is short', () => {
    expect(() =>
      sampleTest({ exam: professional, bank: questions, seen: new Map(), rng: mulberry32(1) }),
    ).toThrow(BankTooSmallError);
  });

  it('is deterministic for a seed and varies across seeds', () => {
    const a = sampleTest({ exam: associate, bank: questions, seen: new Map(), rng: mulberry32(7) });
    const b = sampleTest({ exam: associate, bank: questions, seen: new Map(), rng: mulberry32(7) });
    const c = sampleTest({ exam: associate, bank: questions, seen: new Map(), rng: mulberry32(8) });
    expect(a).toEqual(b);
    expect(a).not.toEqual(c);
  });

  it('never picks two members of one family', () => {
    const base = questions.filter((q) => q.exam === 'associate');
    // Add a variant of every Associate question so each family has two members.
    const variants: Question[] = base.map((q) => ({
      ...q,
      id: `${q.id}-V`,
      variant_of: q.id,
      family: q.id,
    }));
    const bank = [...base, ...variants];
    for (let seed = 0; seed < 20; seed += 1) {
      const ids = sampleTest({ exam: associate, bank, seen: new Map(), rng: mulberry32(seed) });
      const families = ids.map((id) => bank.find((q) => q.id === id)?.family);
      expect(new Set(families).size).toBe(ids.length);
    }
  });

  it('prefers unseen questions and the unseen member of a family', () => {
    const base = questions.filter((q) => q.exam === 'associate');
    const seen = new Map<string, number>();
    // Mark every original as seen; the sampler should reach for something else
    // where it can - here, the variants.
    const variants: Question[] = base.map((q) => ({ ...q, id: `${q.id}-V`, variant_of: q.id, family: q.id }));
    for (const q of base) seen.set(q.id, 2);
    const ids = sampleTest({ exam: associate, bank: [...base, ...variants], seen, rng: mulberry32(3) });
    expect(ids.every((id) => id.endsWith('-V'))).toBe(true);
  });

  it('borrows from other sections when one cannot fill its quota', () => {
    // Keep only one ASSOC-S3 question; S3's quota of 10 must be borrowed elsewhere.
    const bank = questions.filter((q) => q.exam === 'associate' && (q.section !== 'ASSOC-S3' || q.id === 'ASSOC-S3-Q001'));
    const ids = sampleTest({ exam: associate, bank, seen: new Map(), rng: mulberry32(5), items: 40 });
    expect(ids).toHaveLength(40);
    expect(ids.filter((id) => id.startsWith('ASSOC-S3')).length).toBe(1);
  });
});
