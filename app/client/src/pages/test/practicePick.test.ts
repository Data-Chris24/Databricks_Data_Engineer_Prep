import { describe, expect, it } from 'vitest';

import { questionsFor } from '../../../../shared/content';
import { pick } from './Practice';

describe('pick', () => {
  it('draws a new learner from the whole section, not just the first questions in the file', () => {
    const pool = questionsFor('associate', 'ASSOC-S2');
    const seen = new Set<string>();
    for (let i = 0; i < 400; i++) seen.add(pick(pool, {})?.id ?? '');
    expect(seen.size).toBe(pool.length);
  });

  it('still prefers never-seen questions', () => {
    const pool = questionsFor('associate', 'ASSOC-S2');
    const reviews = Object.fromEntries(
      pool.slice(1).map((q) => [
        q.id,
        { questionId: q.id, n: 1, ease: 2.5, dueAt: null, lastRatedAt: null, lastQuality: 3 as const, rightCount: 1, wrongCount: 0 },
      ]),
    );
    for (let i = 0; i < 20; i++) expect(pick(pool, reviews)?.id).toBe(pool[0].id);
  });
});
