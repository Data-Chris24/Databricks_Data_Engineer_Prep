import { describe, expect, it } from 'vitest';

import type { Question } from './types';
import { grade } from './grading';

const q = (id: string, correct: Question['correct']): Question => ({
  id,
  exam: 'associate',
  section: 'ASSOC-S1',
  objectives: ['ASSOC-S1-O1'],
  stem: 'stem',
  code: null,
  options: { A: 'a', B: 'b', C: 'c', D: 'd' },
  correct,
  explanation: 'because',
  why: {},
  difficulty: 'recall',
  provenance: 'original',
  tags: [],
  variant_of: null,
  family: id,
});

const bank = new Map([
  ['Q1', q('Q1', 'A')],
  ['Q2', q('Q2', 'B')],
  ['Q3', q('Q3', 'C')],
]);
const lookup = (id: string) => bank.get(id);

describe('grade', () => {
  it('counts correct answers and treats blanks as wrong', () => {
    const r = grade(['Q1', 'Q2', 'Q3'], { Q1: 'A', Q2: 'D' }, lookup);
    expect(r.correct).toBe(1);
    expect(r.total).toBe(3);
    expect(r.perQuestion).toEqual([
      { id: 'Q1', given: 'A', correct: 'A', isCorrect: true },
      { id: 'Q2', given: 'D', correct: 'B', isCorrect: false },
      { id: 'Q3', given: null, correct: 'C', isCorrect: false },
    ]);
  });

  it('scores an empty answer sheet as zero', () => {
    expect(grade(['Q1', 'Q2'], {}, lookup).correct).toBe(0);
  });

  it('fails loudly if a question vanished from the bank', () => {
    expect(() => grade(['Q9'], {}, lookup)).toThrow(/Q9/);
  });
});
