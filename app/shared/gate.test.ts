import { describe, expect, it } from 'vitest';

import { assignmentGate, gateHint } from './gate';

describe('assignmentGate', () => {
  const lessons = ['a/01', 'a/02', 'a/03'];
  it('stays closed until every lesson notebook was opened', () => {
    const g = assignmentGate(lessons, ['a/01']);
    expect(g.ready).toBe(false);
    expect(g.done).toBe(1);
    expect(g.missing).toEqual(['a/02', 'a/03']);
    expect(gateHint(g)).toBe('The assignment unlocks once all 3 hands-on notebooks have been opened (1 of 3 so far).');
  });
  it('opens when all were opened, in any order, ignoring strangers', () => {
    const g = assignmentGate(lessons, ['a/03', 'x/99', 'a/02', 'a/01']);
    expect(g.ready).toBe(true);
    expect(g.missing).toEqual([]);
    expect(gateHint(g)).toBe('All hands-on notebooks reviewed');
  });
  it('a section without lesson notebooks is open', () => {
    expect(assignmentGate([], []).ready).toBe(true);
  });
});
