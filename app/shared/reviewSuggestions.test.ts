import { describe, expect, it } from 'vitest';

import { examById, notes, questionById, questions } from './content';
import { MAX_SUGGESTIONS, objectiveAnchor, suggestReview } from './reviewSuggestions';

const exam = examById('associate')!;
const inSection = (sid: string) => questions.filter((q) => q.exam === 'associate' && q.section === sid);

describe('suggestReview', () => {
  it('ranks by exam points lost, not by raw percentage', () => {
    // S1 (6%): 1 of 3 wrong = 2 points. S3 (22%): 2 of 10 wrong = 4.4 points.
    const s1 = inSection('ASSOC-S1').slice(0, 3);
    const s3 = inSection('ASSOC-S3').slice(0, 10);
    const results = [
      ...s1.map((q, i) => ({ id: q.id, isCorrect: i > 0 })),
      ...s3.map((q, i) => ({ id: q.id, isCorrect: i > 1 })),
    ];
    const got = suggestReview(exam, results, questionById, notes);
    expect(got.map((s) => s.sectionId)).toEqual(['ASSOC-S3', 'ASSOC-S1']);
    expect(got[0]).toMatchObject({ correct: 8, total: 10 });
    expect(got[0].pointsLost).toBeCloseTo(4.4);
  });

  it('names the missed objectives with a link into the section note', () => {
    const q = inSection('ASSOC-S2')[0];
    const [s] = suggestReview(exam, [{ id: q.id, isCorrect: false }], questionById, notes);
    expect(s.objectives.map((o) => o.id)).toEqual(expect.arrayContaining(q.objectives.filter((o) => o.startsWith('ASSOC-S2'))));
    for (const o of s.objectives) expect(o.anchor).toBeTruthy();
  });

  it('suggests nothing for a perfect score, and at most three sections', () => {
    const all = questions.filter((q) => q.exam === 'associate');
    expect(suggestReview(exam, all.map((q) => ({ id: q.id, isCorrect: true })), questionById, notes)).toEqual([]);
    expect(suggestReview(exam, all.map((q) => ({ id: q.id, isCorrect: false })), questionById, notes)).toHaveLength(MAX_SUGGESTIONS);
  });
});

describe('objectiveAnchor', () => {
  it('finds a heading for every objective of both exams', () => {
    for (const id of ['associate', 'professional'] as const) {
      for (const s of examById(id)!.sections) {
        for (const o of s.objectives) expect(objectiveAnchor(notes[s.id], o.id), o.id).toBeTruthy();
      }
    }
  });
});
