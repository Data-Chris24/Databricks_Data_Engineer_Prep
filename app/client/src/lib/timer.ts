/**
 * Countdown arithmetic that trusts the server's clock, not the browser's.
 *
 * The server sends `serverNow` with every attempt read; the client keeps the
 * offset between that and its own clock and counts down to the deadline the
 * server recorded. A reload, a laptop sleep or a wrong system clock therefore
 * cannot buy or lose time.
 */

export interface Clock {
  offsetMs: number;
  now(): number;
}

export function createClock(serverNowIso: string, localNow: () => number = Date.now): Clock {
  const offsetMs = Date.parse(serverNowIso) - localNow();
  return { offsetMs, now: () => localNow() + offsetMs };
}

export function remainingMs(deadlineIso: string, clock: Clock): number {
  return Math.max(0, Date.parse(deadlineIso) - clock.now());
}

export function formatRemaining(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export type Urgency = 'calm' | 'warn' | 'urgent';

export function urgency(ms: number): Urgency {
  if (ms <= 60_000) return 'urgent';
  if (ms <= 5 * 60_000) return 'warn';
  return 'calm';
}

export function formatDuration(seconds: number): string {
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}
