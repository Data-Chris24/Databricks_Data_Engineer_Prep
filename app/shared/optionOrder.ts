import { NEAR_KEYS, type AuthoredKey, type NearKey, type OptionKey, type Question, type TestLevel } from './types';

/**
 * The order a question's options are shown in, as the stored keys in display
 * order. The bank is authored with the right answer almost always under A
 * (182 of 192 questions on 2026-10-15), so showing options as stored would
 * teach "pick A". Answers are still recorded and scored by stored key; only the
 * letters on screen change.
 */
export type OptionOrder = OptionKey[];

/** The letters shown on screen, whatever keys sit behind them. */
export const LABELS = ['A', 'B', 'C', 'D', 'E', 'F'] as const;
export type Label = (typeof LABELS)[number];

/** FNV-1a: a stable 32-bit hash of a string. */
function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** mulberry32: a small seeded generator, so the same seed always gives the same order. */
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle<T>(items: T[], random: () => number): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function authored(q: Question): AuthoredKey[] {
  return Object.keys(q.options) as AuthoredKey[];
}

function nearKeys(q: Question): NearKey[] {
  return NEAR_KEYS.filter((k) => q.near[k]);
}

/** The text behind any key, authored or near miss. */
export function optionText(q: Question, key: OptionKey): string {
  return (key.startsWith('N') ? q.near[key as NearKey] : q.options[key as AuthoredKey]) ?? '';
}

/** Whether a question can be shown above standard: it needs all three near misses. */
export function hasNearMisses(q: Question): boolean {
  return nearKeys(q).length === NEAR_KEYS.length;
}

/**
 * The options a question shows at a level, unordered. Standard (or a question
 * without near misses): as authored. Medium: the right answer, one near miss and
 * two authored wrong options. Hard: the right answer and the three near misses.
 */
export function optionSet(q: Question, level: TestLevel, random: () => number): OptionKey[] {
  if (level === 'standard' || !hasNearMisses(q)) return authored(q);
  const near = nearKeys(q);
  if (level === 'hard') return [q.correct, ...near];
  const wrong = shuffle(
    authored(q).filter((k) => k !== q.correct),
    random,
  );
  return [q.correct, near[Math.floor(random() * near.length)], ...wrong.slice(0, 2)];
}

/** One question, its level's options shuffled; the same seed and question always give the same order. */
export function shuffledOrder(q: Question, seed: string, level: TestLevel = 'standard'): OptionOrder {
  const random = rng(hash(`${seed}:${q.id}`));
  return shuffle(optionSet(q, level, random), random);
}

/**
 * Orders for a whole timed test. The right answer's position is dealt from an
 * even mix of A, B, C, D across the test, so no letter dominates; the wrong
 * options fill the other places at random. Seeded by the attempt id, so the
 * review shows exactly what the test showed.
 */
export function attemptOrders(questions: Question[], seed: string, level: TestLevel = 'standard'): Record<string, OptionOrder> {
  const random = rng(hash(seed));
  const slots = shuffle(
    questions.map((_, i) => i % 4),
    random,
  );
  const out: Record<string, OptionOrder> = {};
  questions.forEach((q, i) => {
    const others = shuffle(
      optionSet(q, level, random).filter((k) => k !== q.correct),
      random,
    );
    const at = Math.min(slots[i], others.length);
    out[q.id] = [...others.slice(0, at), q.correct, ...others.slice(at)];
  });
  return out;
}

/** The letter shown for a stored key; '?' if the key is not on screen. */
export function labelFor(order: OptionOrder, key: OptionKey): Label | '?' {
  return LABELS[order.indexOf(key)] ?? '?';
}

/** The stored key behind a letter the learner pressed, or null. */
export function keyForLabel(order: OptionOrder, label: string): OptionKey | null {
  const i = LABELS.indexOf(label as Label);
  return i >= 0 && i < order.length ? order[i] : null;
}
