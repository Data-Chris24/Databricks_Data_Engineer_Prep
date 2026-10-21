import { describe, expect, it } from 'vitest';

import { INSERT_ATTEMPT } from './tests';

describe('INSERT_ATTEMPT', () => {
  it('casts the reused time-limit parameter the same way at every use', () => {
    // Postgres deduces one type per parameter; integer column vs make_interval's
    // double precision without a shared cast fails every timed-test start.
    const uses = INSERT_ATTEMPT.match(/\$3(::\w+)?/g) ?? [];
    expect(uses.length).toBe(2);
    expect(new Set(uses)).toEqual(new Set(['$3::int']));
  });
});
