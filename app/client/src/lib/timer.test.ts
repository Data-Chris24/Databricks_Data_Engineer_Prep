import { describe, expect, it } from 'vitest';

import { createClock, formatDuration, formatRemaining, remainingMs, urgency } from './timer';

describe('timer', () => {
  it('counts down from the server clock, not the local one', () => {
    // Local clock is 10 minutes fast; the server says it is T.
    const T = Date.parse('2026-09-10T12:00:00Z');
    let local = T + 10 * 60_000;
    const clock = createClock(new Date(T).toISOString(), () => local);
    const deadline = new Date(T + 90 * 60_000).toISOString();
    expect(remainingMs(deadline, clock)).toBe(90 * 60_000);
    local += 30_000;
    expect(remainingMs(deadline, clock)).toBe(90 * 60_000 - 30_000);
  });

  it('never goes negative', () => {
    const T = Date.parse('2026-09-10T12:00:00Z');
    const clock = createClock(new Date(T).toISOString(), () => T + 1_000_000);
    expect(remainingMs(new Date(T).toISOString(), clock)).toBe(0);
  });

  it('formats mm:ss and h:mm:ss', () => {
    expect(formatRemaining(90 * 60_000)).toBe('1:30:00');
    expect(formatRemaining(5 * 60_000 + 7_000)).toBe('05:07');
    expect(formatRemaining(0)).toBe('00:00');
  });

  it('escalates at five minutes and one minute', () => {
    expect(urgency(10 * 60_000)).toBe('calm');
    expect(urgency(5 * 60_000)).toBe('warn');
    expect(urgency(59_000)).toBe('urgent');
  });

  it('describes durations for the setup screen', () => {
    expect(formatDuration(90 * 60)).toBe('1 h 30 min');
    expect(formatDuration(120 * 60)).toBe('2 h');
    expect(formatDuration(60)).toBe('1 min');
  });
});
