import type { AssignmentGate } from './types';

/**
 * The assignment opens once every hands-on notebook of the section has been
 * opened from the app. Reviewing them is the point of the section; the gate
 * turns that from advice into the path.
 */
export function assignmentGate(lessonPaths: string[], visited: Iterable<string>): AssignmentGate {
  const seen = new Set(visited);
  const missing = lessonPaths.filter((p) => !seen.has(p));
  return { ready: missing.length === 0, done: lessonPaths.length - missing.length, total: lessonPaths.length, missing };
}

export function gateHint(gate: AssignmentGate): string {
  if (gate.ready) return 'All hands-on notebooks reviewed';
  const n = gate.total;
  return `The assignment unlocks once all ${n} hands-on notebook${n === 1 ? '' : 's'} have been opened (${gate.done} of ${n} so far).`;
}
