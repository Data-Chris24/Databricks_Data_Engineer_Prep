import type { OptionKey, PerQuestionResult, Question } from './types';

/**
 * Score an attempt against the answer key. An unanswered question is wrong -
 * the real exam gives no credit for a blank, and neither does a timeout here.
 */
export function grade(
  questionIds: string[],
  answers: Partial<Record<string, OptionKey>>,
  lookup: (id: string) => Question | undefined,
): { correct: number; total: number; perQuestion: PerQuestionResult[] } {
  const perQuestion: PerQuestionResult[] = questionIds.map((id) => {
    const q = lookup(id);
    if (!q) throw new Error(`question ${id} is no longer in the bank`);
    const given = answers[id] ?? null;
    return { id, given, correct: q.correct, isCorrect: given === q.correct };
  });
  const correct = perQuestion.filter((p) => p.isCorrect).length;
  return { correct, total: questionIds.length, perQuestion };
}
