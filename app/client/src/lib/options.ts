import { questionById } from '../../../shared/content';
import { attemptOrders, type OptionOrder } from '../../../shared/optionOrder';
import type { Question, TestLevel } from '../../../shared/types';

/** Option orders for a timed test, the same in the test and its review (seeded by the attempt id). */
export function ordersForAttempt(attempt: {
  attemptId: string;
  questionIds: string[];
  level: TestLevel;
}): Record<string, OptionOrder> {
  const qs = attempt.questionIds.map((id) => questionById(id)).filter((q): q is Question => q !== undefined);
  return attemptOrders(qs, attempt.attemptId, attempt.level);
}
