/**
 * Draw a test at the real exam's shape.
 *
 * Items are apportioned across sections by exam weighting (Hamilton's method,
 * so the quotas sum exactly to the item count), then filled per section from
 * question *families* - a question and its concise variants count as one - so
 * a test never shows both a question and its rewrite. Never-seen families come
 * first; ties break randomly so two tests differ. Sections that cannot fill
 * their quota borrow from the rest of the bank.
 */

import type { Exam, Question } from './types';

export type Rng = () => number;

export class BankTooSmallError extends Error {
  readonly have: number;
  readonly need: number;
  constructor(have: number, need: number) {
    super(`bank has ${have} question families, test needs ${need}`);
    this.name = 'BankTooSmallError';
    this.have = have;
    this.need = need;
  }
}

export function apportion(weights: Record<string, number>, items: number): Record<string, number> {
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  const exact = Object.entries(weights).map(([id, w]) => ({ id, exact: (w / total) * items }));
  const quota: Record<string, number> = {};
  let assigned = 0;
  for (const e of exact) {
    quota[e.id] = Math.floor(e.exact);
    assigned += quota[e.id];
  }
  const remainders = exact
    .map((e) => ({ id: e.id, frac: e.exact - Math.floor(e.exact) }))
    .sort((a, b) => b.frac - a.frac || a.id.localeCompare(b.id));
  for (let i = 0; i < items - assigned; i += 1) {
    quota[remainders[i % remainders.length].id] += 1;
  }
  return quota;
}

function shuffle<T>(arr: T[], rng: Rng): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

interface Family {
  id: string;
  section: string;
  members: Question[];
  minSeen: number;
}

export interface SampleInput {
  exam: Exam;
  bank: Question[];
  /** questionId -> how many times this user has met it (practice + tests). */
  seen: Map<string, number>;
  rng?: Rng;
  /** Override the item count (tests only); defaults to the exam's scored items. */
  items?: number;
}

export function sampleTest({ exam, bank, seen, rng = Math.random, items }: SampleInput): string[] {
  const count = items ?? exam.items;
  const pool = bank.filter((q) => q.exam === exam.id);

  const byFamily = new Map<string, Family>();
  for (const q of pool) {
    const fam = byFamily.get(q.family) ?? { id: q.family, section: q.section, members: [], minSeen: 0 };
    fam.members.push(q);
    byFamily.set(q.family, fam);
  }
  for (const fam of byFamily.values()) {
    // The family's section is its root's section; members share a primary objective.
    const root = fam.members.find((m) => m.id === fam.id) ?? fam.members[0];
    fam.section = root.section;
    fam.minSeen = Math.min(...fam.members.map((m) => seen.get(m.id) ?? 0));
  }
  if (byFamily.size < count) throw new BankTooSmallError(byFamily.size, count);

  const weights = Object.fromEntries(exam.sections.map((s) => [s.id, s.weight]));
  const quota = apportion(weights, count);

  // Randomise once, then sort by exposure: stable sort keeps the random order
  // among equally-seen families.
  const order = (fams: Family[]) => shuffle(fams, rng).sort((a, b) => a.minSeen - b.minSeen);

  const picked: Family[] = [];
  const taken = new Set<string>();
  let shortfall = 0;
  for (const s of exam.sections) {
    const candidates = order([...byFamily.values()].filter((f) => f.section === s.id));
    const take = Math.min(quota[s.id] ?? 0, candidates.length);
    for (const f of candidates.slice(0, take)) {
      picked.push(f);
      taken.add(f.id);
    }
    shortfall += (quota[s.id] ?? 0) - take;
  }
  if (shortfall > 0) {
    const rest = order([...byFamily.values()].filter((f) => !taken.has(f.id)));
    for (const f of rest.slice(0, shortfall)) {
      picked.push(f);
      taken.add(f.id);
    }
  }

  const chosen = picked.map((f) => {
    const unseen = f.members.filter((m) => (seen.get(m.id) ?? 0) === 0);
    if (unseen.length === 1) return unseen[0].id;
    const from = unseen.length ? unseen : f.members;
    return from[Math.floor(rng() * from.length)].id;
  });
  return shuffle(chosen, rng);
}

/** Small deterministic generator for tests and reproducible draws. */
export function mulberry32(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
