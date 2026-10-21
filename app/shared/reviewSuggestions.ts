import type { Exam, PerQuestionResult, Question, SectionNote } from './types';

/**
 * What to review after a timed test, ranked by exam points lost: a section's
 * weight times the share of its questions missed. Missing one of S3's ten
 * questions (22% of the exam) outranks missing one of S1's three (6%), which a
 * plain per-section percentage would get backwards.
 *
 * One test gives a section only a handful of questions (ASSOC-S1 about 3), so
 * each suggestion carries its question count for the page to show.
 */
export interface MissedObjective {
  id: string;
  text: string;
  /** Questions on this objective answered wrong or left blank. */
  missed: number;
  /** Heading in the section note that covers it, for a deep link. */
  anchor: string | null;
}

export interface ReviewSuggestion {
  sectionId: string;
  number: number;
  title: string;
  weight: number;
  correct: number;
  total: number;
  /** Percentage points of the real exam this section's misses stand for. */
  pointsLost: number;
  objectives: MissedObjective[];
}

export const MAX_SUGGESTIONS = 3;

/** The note heading that covers an objective, or null. */
export function objectiveAnchor(note: SectionNote | undefined, objectiveId: string): string | null {
  return note?.toc.find((t) => t.objective_ids.includes(objectiveId))?.anchor ?? null;
}

export function suggestReview(
  exam: Exam,
  perQuestion: Pick<PerQuestionResult, 'id' | 'isCorrect'>[],
  lookup: (id: string) => Question | undefined,
  notes: Record<string, SectionNote>,
): ReviewSuggestion[] {
  const out: ReviewSuggestion[] = [];
  for (const s of exam.sections) {
    const rows = perQuestion.map((p) => ({ ...p, q: lookup(p.id) })).filter((r) => r.q?.section === s.id);
    const wrong = rows.filter((r) => !r.isCorrect);
    if (!rows.length || !wrong.length) continue;

    const missed = new Map<string, number>();
    for (const r of wrong) for (const o of r.q?.objectives ?? []) missed.set(o, (missed.get(o) ?? 0) + 1);
    const objectives = s.objectives
      .filter((o) => missed.has(o.id))
      .map((o) => ({ id: o.id, text: o.text, missed: missed.get(o.id) ?? 0, anchor: objectiveAnchor(notes[s.id], o.id) }))
      .sort((a, b) => b.missed - a.missed);

    out.push({
      sectionId: s.id,
      number: s.number,
      title: s.title,
      weight: s.weight,
      correct: rows.length - wrong.length,
      total: rows.length,
      pointsLost: (s.weight * wrong.length) / rows.length,
      objectives,
    });
  }
  return out.sort((a, b) => b.pointsLost - a.pointsLost || b.weight - a.weight).slice(0, MAX_SUGGESTIONS);
}
