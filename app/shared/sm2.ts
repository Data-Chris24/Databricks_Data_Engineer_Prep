/**
 * SM-2 lite spaced repetition, ported unchanged from the original study page.
 *
 * quality: 0 Again, 1 Hard, 2 Good, 3 Easy. "Again" resets the streak and
 * lowers ease; anything else advances it. Gaps grow 1 day, 3 days, then by
 * ease. The constants are deliberately the same as before so existing habits
 * (and the tests that pin them) carry over.
 */

import type { Quality } from './types';

export const DAY_MS = 86_400_000;

export interface ReviewState {
  n: number;
  ease: number;
  dueAt: number | null; // epoch ms
  lastRatedAt: number | null;
  lastQuality: Quality | null;
  rightCount: number;
  wrongCount: number;
}

export const FRESH: ReviewState = {
  n: 0,
  ease: 2.5,
  dueAt: null,
  lastRatedAt: null,
  lastQuality: null,
  rightCount: 0,
  wrongCount: 0,
};

export function gapDays(n: number, ease: number): number {
  if (n === 0) return 0;
  if (n === 1) return 1;
  if (n === 2) return 3;
  return Math.round((n - 1) * ease * 1.6);
}

export function schedule(prev: ReviewState | null, quality: Quality, now = Date.now()): ReviewState {
  const s = { ...(prev ?? FRESH) };
  if (quality === 0) {
    s.n = 0;
    s.ease = Math.max(1.3, s.ease - 0.2);
    s.wrongCount += 1;
  } else {
    s.n += 1;
    s.ease = Math.min(2.8, Math.max(1.3, s.ease + (quality - 2) * 0.15));
    s.rightCount += 1;
  }
  s.dueAt = now + gapDays(s.n, s.ease) * DAY_MS;
  s.lastRatedAt = now;
  s.lastQuality = quality;
  return s;
}

export function isDue(state: ReviewState | undefined, now = Date.now()): boolean {
  return !state || state.dueAt === null || state.dueAt <= now;
}
