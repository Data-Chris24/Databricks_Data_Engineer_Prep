import type { ProgressRow } from './types';

/**
 * A section is complete when its assignment has passed, not when the notes
 * have been read to the end. Reading is still tracked (`read`) for the
 * resume point and the "in progress" state; completion is derived here from
 * the grading history, so a reset that deletes the grading runs also takes the
 * completion away, and nothing has to remember to flip a flag.
 */
export function blankProgress(sectionId: string, at: string): ProgressRow {
  return { sectionId, visited: false, read: false, completed: false, completedAt: null, lastAnchor: null, scrollPct: null, lastSeen: at };
}

export function applyCompletion(
  sections: Record<string, ProgressRow>,
  passedAt: Record<string, string>,
  sectionIds: string[],
): { sections: Record<string, ProgressRow>; completed: number; percentComplete: number } {
  const out: Record<string, ProgressRow> = {};
  let completed = 0;
  for (const id of sectionIds) {
    const row = sections[id];
    const at = passedAt[id];
    if (at) {
      out[id] = { ...(row ?? blankProgress(id, at)), completed: true, completedAt: at };
      completed += 1;
    } else if (row) {
      out[id] = { ...row, completed: false, completedAt: null };
    }
  }
  return { sections: out, completed, percentComplete: sectionIds.length ? Math.round((completed / sectionIds.length) * 100) : 0 };
}
