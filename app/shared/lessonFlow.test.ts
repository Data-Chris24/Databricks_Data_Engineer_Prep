import { describe, expect, it } from 'vitest';

import { lessonDestination } from './lessonFlow';

const S = [1, 2, 3].map((n) => ({ id: `X-S${n}`, number: n, title: `Section ${n}` }));

describe('lessonDestination', () => {
  it('returns to the current section while its assignment has not passed', () => {
    expect(lessonDestination(S, 'X-S2', new Set())).toEqual({ kind: 'section', section: S[1], why: 'continue' });
  });
  it('moves on to the next unfinished section once the current one is complete', () => {
    expect(lessonDestination(S, 'X-S1', new Set(['X-S1']))).toEqual({ kind: 'section', section: S[1], why: 'next' });
    expect(lessonDestination(S, 'X-S2', new Set(['X-S2', 'X-S3']))).toEqual({ kind: 'section', section: S[0], why: 'next' });
  });
  it('goes to the Learn home when everything is complete or no section was chosen', () => {
    expect(lessonDestination(S, 'X-S3', new Set(['X-S1', 'X-S2', 'X-S3']))).toEqual({ kind: 'home', why: 'all_done' });
    expect(lessonDestination(S, null, new Set())).toEqual({ kind: 'home', why: 'no_section' });
    expect(lessonDestination(S, 'nope', new Set())).toEqual({ kind: 'home', why: 'no_section' });
  });
});
