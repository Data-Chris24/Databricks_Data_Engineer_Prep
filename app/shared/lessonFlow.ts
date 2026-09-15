/**
 * Where "back to the lesson" goes after a practice batch. A section is done
 * when its assignment has passed (shared/completion.ts), so: from a finished
 * section, on to the next unfinished one in exam order; from an unfinished
 * one, back into it; with nothing left, the Learn home.
 */
export interface FlowSection {
  id: string;
  number: number;
  title: string;
}

export type LessonDestination =
  | { kind: 'section'; section: FlowSection; why: 'continue' | 'next' }
  | { kind: 'home'; why: 'all_done' | 'no_section' };

export function lessonDestination(sections: FlowSection[], currentId: string | null, completed: Set<string>): LessonDestination {
  if (!currentId) return { kind: 'home', why: 'no_section' };
  const idx = sections.findIndex((s) => s.id === currentId);
  const current = idx >= 0 ? sections[idx] : null;
  if (!current) return { kind: 'home', why: 'no_section' };
  if (!completed.has(current.id)) return { kind: 'section', section: current, why: 'continue' };
  const after = sections.slice(idx + 1).find((s) => !completed.has(s.id)) ?? sections.find((s) => !completed.has(s.id));
  return after ? { kind: 'section', section: after, why: 'next' } : { kind: 'home', why: 'all_done' };
}
