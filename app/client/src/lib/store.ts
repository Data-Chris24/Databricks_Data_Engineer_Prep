/**
 * The one door to persistence. Every screen reads and writes through a
 * StudyStore; ApiStore talks to the server, MemoryStore keeps everything in
 * process for tests and for running the UI without a database.
 */

import { createContext, useContext } from 'react';

import { examById, lessonPaths, questionById, questions, starters } from '../../../shared/content';
import { grade } from '../../../shared/grading';
import { sampleTest, BankTooSmallError as SamplerBankTooSmall } from '../../../shared/sampler';
import { assignmentGate } from '../../../shared/gate';
import { schedule, type ReviewState } from '../../../shared/sm2';
import { meta } from '../../../shared/content';
import type {
  AppConfig,
  Area,
  AssignmentState,
  Attempt,
  AttemptStart,
  AttemptSummary,
  ExamId,
  GradingRun,
  Me,
  OptionKey,
  ProgressPatch,
  ProgressRow,
  Quality,
  ResetAllResult,
  ReviewRow,
  ScoreResult,
  TrainingState,
} from '../../../shared/types';

export class ApiError extends Error {
  readonly status: number;
  readonly body: Record<string, unknown>;
  constructor(status: number, body: Record<string, unknown>) {
    super(typeof body.error === 'string' ? body.error : `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export class BankTooSmallError extends ApiError {
  readonly have: number;
  readonly need: number;
  constructor(have: number, need: number) {
    super(409, { error: 'bank_too_small', have, need });
    this.name = 'BankTooSmallError';
    this.have = have;
    this.need = need;
  }
}

export class GradingInProgressError extends ApiError {
  readonly run: GradingRun;
  constructor(run: GradingRun) {
    super(409, { error: 'grading_in_progress' });
    this.name = 'GradingInProgressError';
    this.run = run;
  }
}

export class LessonsUnvisitedError extends ApiError {
  readonly gate: AssignmentState['gate'];
  constructor(gate: AssignmentState['gate']) {
    super(409, { error: 'lessons_unvisited' });
    this.name = 'LessonsUnvisitedError';
    this.gate = gate;
  }
}

export class AttemptActiveError extends ApiError {
  readonly attemptId: string;
  constructor(attemptId: string) {
    super(409, { error: 'attempt_active', attemptId });
    this.name = 'AttemptActiveError';
    this.attemptId = attemptId;
  }
}

export interface StudyStore {
  me(): Promise<Me>;
  setLastArea(area: Area): Promise<void>;
  config(): Promise<AppConfig>;
  training(exam: ExamId): Promise<TrainingState>;
  touchSection(exam: ExamId, sectionId: string, patch: ProgressPatch): Promise<ProgressRow>;
  resetTraining(exam: ExamId): Promise<void>;
  practiceState(exam: ExamId): Promise<Record<string, ReviewRow>>;
  rate(questionId: string, quality: Quality): Promise<ReviewRow>;
  attempts(exam: ExamId): Promise<{ history: AttemptSummary[]; activeId: string | null }>;
  startAttempt(exam: ExamId, opts?: { timeLimitSecondsOverride?: number }): Promise<AttemptStart>;
  attempt(id: string): Promise<Attempt>;
  answer(id: string, questionId: string, key: OptionKey): Promise<void>;
  submit(id: string, auto: boolean): Promise<ScoreResult>;
  /** Latest grading run per section of the exam. */
  grading(exam: ExamId): Promise<Record<string, GradingRun>>;
  /** Latest grading run for a section, refreshed against the job; configured=false means no job is bound. */
  gradingRun(sectionId: string): Promise<{ run: GradingRun | null; configured: boolean }>;
  /** Trigger the section's grading job. */
  grade(sectionId: string): Promise<GradingRun>;
  /** Record that a lesson notebook was opened from the app. */
  visitNotebook(path: string): Promise<void>;
  assignment(sectionId: string): Promise<AssignmentState>;
  /** Create the learner's own copy of the starter notebooks (idempotent). */
  provisionAssignment(sectionId: string): Promise<AssignmentState>;
  /** Overwrite the learner's copy with the starter again. */
  resetAssignment(sectionId: string): Promise<AssignmentState>;
  /** Reset every assignment of the exam: starters, output tables and grades. */
  resetAllAssignments(exam: ExamId): Promise<ResetAllResult>;
}

// ------------------------------------------------------------------ api

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  if (!res.ok) {
    if (data.error === 'bank_too_small') throw new BankTooSmallError(Number(data.have), Number(data.need));
    if (data.error === 'attempt_active') throw new AttemptActiveError(String(data.attemptId));
    if (data.error === 'grading_in_progress') throw new GradingInProgressError(data.run as GradingRun);
    if (data.error === 'lessons_unvisited') throw new LessonsUnvisitedError(data.gate as AssignmentState['gate']);
    throw new ApiError(res.status, data);
  }
  return data as T;
}

export class ApiStore implements StudyStore {
  me() {
    return request<Me>('GET', '/api/me');
  }
  setLastArea(area: Area) {
    return request<void>('PUT', '/api/me/last-area', { area });
  }
  config() {
    return request<AppConfig>('GET', '/api/config');
  }
  training(exam: ExamId) {
    return request<TrainingState>('GET', `/api/training/${exam}`);
  }
  touchSection(exam: ExamId, sectionId: string, patch: ProgressPatch) {
    return request<ProgressRow>('PUT', `/api/training/${exam}/sections/${sectionId}`, patch);
  }
  resetTraining(exam: ExamId) {
    return request<void>('POST', `/api/training/${exam}/reset`);
  }
  practiceState(exam: ExamId) {
    return request<Record<string, ReviewRow>>('GET', `/api/practice/${exam}/state`);
  }
  rate(questionId: string, quality: Quality) {
    return request<ReviewRow>('POST', '/api/practice/rate', { questionId, quality });
  }
  attempts(exam: ExamId) {
    return request<{ history: AttemptSummary[]; activeId: string | null }>('GET', `/api/tests/${exam}/attempts`);
  }
  startAttempt(exam: ExamId, opts?: { timeLimitSecondsOverride?: number }) {
    return request<AttemptStart>('POST', `/api/tests/${exam}/attempts`, opts ?? {});
  }
  attempt(id: string) {
    return request<Attempt>('GET', `/api/tests/attempts/${id}`);
  }
  answer(id: string, questionId: string, key: OptionKey) {
    return request<void>('PUT', `/api/tests/attempts/${id}/answers`, { questionId, key });
  }
  submit(id: string, auto: boolean) {
    return request<ScoreResult>('POST', `/api/tests/attempts/${id}/submit`, { auto });
  }
  grading(exam: ExamId) {
    return request<Record<string, GradingRun>>('GET', `/api/grading/exam/${exam}`);
  }
  gradingRun(sectionId: string) {
    return request<{ run: GradingRun | null; configured: boolean }>('GET', `/api/grading/section/${sectionId}`);
  }
  grade(sectionId: string) {
    return request<GradingRun>('POST', `/api/grading/section/${sectionId}/run`);
  }
  visitNotebook(path: string) {
    return request<void>('PUT', '/api/training/visits', { path });
  }
  assignment(sectionId: string) {
    return request<AssignmentState>('GET', `/api/assignment/${sectionId}`);
  }
  provisionAssignment(sectionId: string) {
    return request<AssignmentState>('POST', `/api/assignment/${sectionId}/provision`);
  }
  resetAssignment(sectionId: string) {
    return request<AssignmentState>('POST', `/api/assignment/${sectionId}/reset`);
  }
  resetAllAssignments(exam: ExamId) {
    return request<ResetAllResult>('POST', `/api/assignment/reset-all/${exam}`);
  }
}

// --------------------------------------------------------------- memory

interface MemoryAttempt extends AttemptSummary {
  questionIds: string[];
  answers: Partial<Record<string, OptionKey>>;
}

export interface MemoryOptions {
  lastArea?: Area | null;
  now?: () => number;
  config?: Partial<AppConfig>;
}

// The interface is Promise-shaped because the real store is; the in-memory one
// has nothing to await, which is exactly the point of it.
/* eslint-disable @typescript-eslint/require-await */
export class MemoryStore implements StudyStore {
  private lastArea: Area | null;
  private readonly now: () => number;
  private readonly cfg: AppConfig;
  private progress = new Map<string, ProgressRow & { exam: ExamId }>();
  private review = new Map<string, ReviewState>();
  private attemptsById = new Map<string, MemoryAttempt>();
  private gradingRuns = new Map<string, GradingRun>();
  private visits = new Set<string>();
  private copies = new Map<string, { folder: string; notebook: string; resetCount: number }>();
  private seq = 0;

  constructor(opts: MemoryOptions = {}) {
    this.lastArea = opts.lastArea ?? null;
    this.now = opts.now ?? Date.now;
    this.cfg = {
      workspaceHost: null,
      filesRoot: null,
      contentVersion: meta.content_version,
      ...opts.config,
    };
  }

  async me(): Promise<Me> {
    return { userId: 'local@example.com', displayName: 'Local', lastArea: this.lastArea };
  }
  async setLastArea(area: Area) {
    this.lastArea = area;
  }
  async config() {
    return this.cfg;
  }

  async training(exam: ExamId): Promise<TrainingState> {
    const ex = examById(exam);
    if (!ex) throw new ApiError(404, { error: 'unknown_exam' });
    const rows = [...this.progress.values()].filter((r) => r.exam === exam);
    rows.sort((a, b) => b.lastSeen.localeCompare(a.lastSeen));
    const sections: Record<string, ProgressRow> = {};
    for (const r of rows) sections[r.sectionId] = r;
    const completed = rows.filter((r) => r.completed).length;
    const paths = new Set(ex.sections.flatMap((s) => lessonPaths(s.id)));
    return {
      sections,
      resume: rows[0] ? { sectionId: rows[0].sectionId, anchor: rows[0].lastAnchor } : null,
      percentComplete: Math.round((completed / ex.sections.length) * 100),
      visited: [...this.visits].filter((p) => paths.has(p)),
    };
  }
  async touchSection(exam: ExamId, sectionId: string, patch: ProgressPatch): Promise<ProgressRow> {
    const key = `${exam}:${sectionId}`;
    const prev = this.progress.get(key);
    const nowIso = new Date(this.now()).toISOString();
    const completed = patch.completed ?? prev?.completed ?? false;
    const row = {
      exam,
      sectionId,
      visited: true,
      completed,
      completedAt: completed ? (prev?.completedAt ?? nowIso) : null,
      lastAnchor: patch.anchor ?? prev?.lastAnchor ?? null,
      scrollPct: patch.scrollPct ?? prev?.scrollPct ?? null,
      lastSeen: nowIso,
    };
    this.progress.set(key, row);
    return row;
  }
  async resetTraining(exam: ExamId) {
    for (const k of [...this.progress.keys()]) if (k.startsWith(`${exam}:`)) this.progress.delete(k);
    const paths = new Set(examById(exam)?.sections.flatMap((s) => lessonPaths(s.id)) ?? []);
    for (const p of [...this.visits]) if (paths.has(p)) this.visits.delete(p);
  }
  async visitNotebook(path: string) {
    this.visits.add(path);
  }
  async assignment(sectionId: string): Promise<AssignmentState> {
    const copy = this.copies.get(sectionId);
    return {
      sectionId,
      hasStarters: (starters[sectionId] ?? []).length > 0,
      provisioned: Boolean(copy?.notebook),
      folder: copy?.folder || null,
      notebook: copy?.notebook || null,
      resetCount: copy?.resetCount ?? 0,
      resetting: false,
      gate: assignmentGate(lessonPaths(sectionId), this.visits),
    };
  }
  async provisionAssignment(sectionId: string) {
    const s = await this.assignment(sectionId);
    if (!s.gate.ready) throw new LessonsUnvisitedError(s.gate);
    if (!s.hasStarters) throw new ApiError(404, { error: 'no_starter' });
    if (!this.copies.has(sectionId)) {
      const folder = `/Users/memory/learners/local@example.com/${sectionId}`;
      const main = starters[sectionId].find((x) => x.name === 'assignment') ?? starters[sectionId][0];
      this.copies.set(sectionId, { folder, notebook: `${folder}/${main.name}`, resetCount: 0 });
    }
    return this.assignment(sectionId);
  }
  async resetAssignment(sectionId: string) {
    const copy = this.copies.get(sectionId);
    if (copy) copy.resetCount += 1;
    else this.copies.set(sectionId, { folder: '', notebook: '', resetCount: 1 });
    this.gradingRuns.delete(sectionId);
    return this.assignment(sectionId);
  }
  async resetAllAssignments(exam: ExamId): Promise<ResetAllResult> {
    const sections = examById(exam)?.sections.map((s) => s.id) ?? [];
    for (const sid of sections) {
      const copy = this.copies.get(sid);
      if (copy) copy.resetCount += 1;
      this.gradingRuns.delete(sid);
    }
    return { exam, sections, runId: null };
  }

  async practiceState(exam: ExamId) {
    const out: Record<string, ReviewRow> = {};
    for (const [id, s] of this.review) {
      const q = questionById(id);
      if (q && q.exam === exam) out[id] = toReviewRow(id, s);
    }
    return out;
  }
  async rate(questionId: string, quality: Quality) {
    const next = schedule(this.review.get(questionId) ?? null, quality, this.now());
    this.review.set(questionId, next);
    return toReviewRow(questionId, next);
  }

  async attempts(exam: ExamId) {
    const history = [...this.attemptsById.values()]
      .filter((a) => a.exam === exam)
      .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
      .map(({ questionIds: _q, answers: _a, ...summary }) => summary);
    const active = history.find((a) => a.submittedAt === null);
    return { history, activeId: active?.attemptId ?? null };
  }
  async startAttempt(exam: ExamId, opts?: { timeLimitSecondsOverride?: number }): Promise<AttemptStart> {
    const ex = examById(exam);
    if (!ex) throw new ApiError(404, { error: 'unknown_exam' });
    const active = [...this.attemptsById.values()].find((a) => a.exam === exam && !a.submittedAt);
    if (active) throw new AttemptActiveError(active.attemptId);
    const seen = new Map<string, number>();
    for (const [id, s] of this.review) seen.set(id, s.rightCount + s.wrongCount);
    for (const a of this.attemptsById.values()) for (const id of a.questionIds) seen.set(id, (seen.get(id) ?? 0) + 1);
    let questionIds: string[];
    try {
      questionIds = sampleTest({ exam: ex, bank: questions, seen });
    } catch (err) {
      if (err instanceof SamplerBankTooSmall) throw new BankTooSmallError(err.have, err.need);
      throw err;
    }
    const limit = Math.min(opts?.timeLimitSecondsOverride ?? ex.minutes * 60, ex.minutes * 60);
    const started = this.now();
    this.seq += 1;
    const attempt: MemoryAttempt = {
      attemptId: `mem-${this.seq}`,
      exam,
      startedAt: new Date(started).toISOString(),
      deadlineAt: new Date(started + limit * 1000).toISOString(),
      submittedAt: null,
      autoSubmitted: false,
      timeLimitSeconds: limit,
      scoreCorrect: null,
      scoreTotal: questionIds.length,
      contentVersion: meta.content_version,
      questionIds,
      answers: {},
    };
    this.attemptsById.set(attempt.attemptId, attempt);
    return {
      attemptId: attempt.attemptId,
      questionIds,
      startedAt: attempt.startedAt,
      deadlineAt: attempt.deadlineAt,
      serverNow: new Date(started).toISOString(),
    };
  }
  async attempt(id: string): Promise<Attempt> {
    const a = this.attemptsById.get(id);
    if (!a) throw new ApiError(404, { error: 'unknown_attempt' });
    if (!a.submittedAt && this.now() > Date.parse(a.deadlineAt) + 5000) await this.submit(id, true);
    return { ...a, serverNow: new Date(this.now()).toISOString() };
  }
  async answer(id: string, questionId: string, key: OptionKey) {
    const a = this.attemptsById.get(id);
    if (!a) throw new ApiError(404, { error: 'unknown_attempt' });
    if (a.submittedAt) throw new ApiError(409, { error: 'attempt_closed' });
    if (this.now() > Date.parse(a.deadlineAt) + 5000) throw new ApiError(409, { error: 'attempt_expired' });
    a.answers[questionId] = key;
  }
  async submit(id: string, auto: boolean): Promise<ScoreResult> {
    const a = this.attemptsById.get(id);
    if (!a) throw new ApiError(404, { error: 'unknown_attempt' });
    const result = grade(a.questionIds, a.answers, questionById);
    if (!a.submittedAt) {
      a.submittedAt = new Date(this.now()).toISOString();
      a.autoSubmitted = auto || this.now() > Date.parse(a.deadlineAt);
      a.scoreCorrect = result.correct;
    }
    return {
      attemptId: id,
      scoreCorrect: result.correct,
      scoreTotal: result.total,
      autoSubmitted: a.autoSubmitted,
      submittedAt: a.submittedAt,
      perQuestion: result.perQuestion,
    };
  }

  private settleGrading(run: GradingRun): GradingRun {
    // A pretend grader: finishes a few seconds after it starts, passing.
    if (run.status !== 'running' || this.now() - Date.parse(run.startedAt) < 3000) return run;
    const done: GradingRun = {
      ...run,
      status: 'passed',
      finishedAt: new Date(this.now()).toISOString(),
      result: { section: run.sectionId, passed: true, total: 3, failed: [], tests: [], report_tail: '3 passed' },
    };
    this.gradingRuns.set(run.sectionId, done);
    return done;
  }
  async grading(exam: ExamId) {
    const ex = examById(exam);
    const out: Record<string, GradingRun> = {};
    for (const [sid, run] of this.gradingRuns) if (ex?.sections.some((s) => s.id === sid)) out[sid] = this.settleGrading(run);
    return out;
  }
  async gradingRun(sectionId: string) {
    const run = this.gradingRuns.get(sectionId);
    return { run: run ? this.settleGrading(run) : null, configured: true };
  }
  async grade(sectionId: string): Promise<GradingRun> {
    const current = this.gradingRuns.get(sectionId);
    if (current && this.settleGrading(current).status === 'running') throw new GradingInProgressError(current);
    this.seq += 1;
    const run: GradingRun = {
      id: `grade-${this.seq}`,
      sectionId,
      runId: this.seq,
      status: 'running',
      startedAt: new Date(this.now()).toISOString(),
      finishedAt: null,
      result: null,
      error: null,
    };
    this.gradingRuns.set(sectionId, run);
    return run;
  }
}

/* eslint-enable @typescript-eslint/require-await */

function toReviewRow(questionId: string, s: ReviewState): ReviewRow {
  return {
    questionId,
    n: s.n,
    ease: s.ease,
    dueAt: s.dueAt === null ? null : new Date(s.dueAt).toISOString(),
    lastRatedAt: s.lastRatedAt === null ? null : new Date(s.lastRatedAt).toISOString(),
    lastQuality: s.lastQuality,
    rightCount: s.rightCount,
    wrongCount: s.wrongCount,
  };
}

// ---------------------------------------------------------------- react

export const StoreContext = createContext<StudyStore | null>(null);

export function useStore(): StudyStore {
  const store = useContext(StoreContext);
  if (!store) throw new Error('StoreContext is not provided');
  return store;
}
