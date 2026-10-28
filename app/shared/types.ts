import type { UnitResources } from './units';

/**
 * Types shared by the server and the client.
 *
 * The content types mirror the JSON that tools/build_app_content.py writes into
 * shared/content/. The API types are the wire shapes of the routes in
 * server/routes/, which the client's StudyStore consumes.
 */

export type ExamId = 'associate' | 'professional';
export type Area = 'learn' | 'test';
/** Authored options are A-F; a question's near-miss distractors are N1-N3. */
export type AuthoredKey = 'A' | 'B' | 'C' | 'D' | 'E' | 'F';
export type NearKey = 'N1' | 'N2' | 'N3';
export type OptionKey = AuthoredKey | NearKey;
export const NEAR_KEYS: NearKey[] = ['N1', 'N2', 'N3'];

/**
 * How tricky a test's wrong options are. Standard shows a question as authored;
 * medium swaps one wrong option for a near miss (shaped like the right answer,
 * one detail wrong); hard shows only near misses. A question with no near
 * misses yet shows as authored at every level. See shared/optionOrder.ts.
 */
export type TestLevel = 'standard' | 'medium' | 'hard';
export const TEST_LEVELS: TestLevel[] = ['standard', 'medium', 'hard'];

// ---------------------------------------------------------------- content

export interface ObjectiveSummary {
  id: string;
  text: string;
  lab: 'full' | 'partial' | 'theory_only';
}

export interface SectionSummary {
  id: string;
  number: number;
  title: string;
  weight: number;
  objectives: ObjectiveSummary[];
}

export interface Exam {
  id: ExamId;
  name: string;
  short: 'Associate' | 'Professional';
  items: number;
  minutes: number;
  guide: string;
  sections: SectionSummary[];
  /** Every tracked guide version, oldest first; the fields above are the latest. */
  versions: GuideVersionSnapshot[];
}

/** The objective map as one guide version printed it. */
export interface GuideVersionSnapshot {
  guide: string;
  items: number;
  weightingSource: string;
  sections: SectionSummary[];
}

export interface Question {
  id: string;
  exam: ExamId;
  section: string;
  objectives: string[];
  stem: string;
  code: string | null;
  options: Partial<Record<AuthoredKey, string>>;
  correct: AuthoredKey;
  explanation: string;
  /** Why each wrong option is wrong, near misses included. */
  why: Partial<Record<OptionKey, string>>;
  /** Wrong options shaped like the right answer, for medium and hard tests; empty when none yet. */
  near: Partial<Record<NearKey, string>>;
  /** 'code' when the options are code fragments, shown in monospace. */
  optionStyle: 'text' | 'code';
  /** Language of `code`, for its label: a fill-in-the-blank snippet marks the gap with ____. */
  codeLanguage: 'python' | 'sql' | null;
  difficulty: 'recall' | 'application' | 'analysis';
  provenance: 'original' | 'official-sample' | 'concept-inspired';
  tags: string[];
  variant_of: string | null;
  /** Root of the variant chain. Test mode draws one question per family. */
  family: string;
}

export interface TocEntry {
  level: 2 | 3;
  text: string;
  anchor: string;
  objective_ids: string[];
}

export interface SubPage {
  slug: string;
  title: string;
  objective_ids: string[];
  markdown: string;
  toc: TocEntry[];
}

export interface SectionNote {
  section_id: string;
  exam: ExamId;
  title: string;
  weight: number;
  markdown: string;
  toc: TocEntry[];
  subpages: SubPage[];
}

export interface LessonNotebook {
  path: string;
  title: string;
  /** Listed with an Optional badge; the section's assignment does not wait for it. */
  optional?: boolean;
}

/**
 * An optional assignment beside a section's own (e.g. ASSOC-S2-AUTO-LOADER).
 * Graded, provisioned and reset like the section's, under its own id; it never
 * counts toward completing the section.
 */
export interface ExtraAssignment {
  id: string;
  title: string;
  readme: string;
  notebook: string;
  grade_job: string;
  /** Lesson paths that must have been opened first: every lesson of the section. */
  gate: string[];
}

export interface SectionNotebooks {
  lessons: LessonNotebook[];
  assignment: {
    readme: string | null;
    notebook: string | null;
    grade_job: string | null;
  };
  extras: ExtraAssignment[];
  /** The bundle job that sets the unit up (generates its teach and assess data). */
  datasets: { job: string | null };
  /** What the unit creates in the workspace (grading/<SECTION>/resources.json). */
  resources: UnitResources;
}

export interface ContentMeta {
  content_version: string;
  question_count: number;
  families_per_exam: Record<ExamId, number>;
  notes_count: number;
}

// ---------------------------------------------------------------- api

export interface Me {
  userId: string;
  displayName: string | null;
  lastArea: Area | null;
}

export interface AppConfig {
  workspaceHost: string | null;
  filesRoot: string | null;
  contentVersion: string;
}

export interface ProgressRow {
  sectionId: string;
  visited: boolean;
  /** The notes were read to the end (the page's end sentinel was in view). */
  read: boolean;
  /** The assignment has a passing grade; derived from grading runs, never set directly. */
  completed: boolean;
  completedAt: string | null;
  lastAnchor: string | null;
  scrollPct: number | null;
  lastSeen: string;
}

export interface TrainingState {
  sections: Record<string, ProgressRow>;
  resume: { sectionId: string; anchor: string | null } | null;
  percentComplete: number;
  /** Lesson notebook paths (repo-relative) this user has opened from the app. */
  visited: string[];
}

export interface ProgressPatch {
  anchor?: string;
  scrollPct?: number;
  read?: boolean;
}

export interface ReviewRow {
  questionId: string;
  n: number;
  ease: number;
  dueAt: string | null;
  lastRatedAt: string | null;
  lastQuality: number | null;
  rightCount: number;
  wrongCount: number;
}

export type Quality = 0 | 1 | 2 | 3;

export interface AttemptSummary {
  attemptId: string;
  exam: ExamId;
  startedAt: string;
  deadlineAt: string;
  submittedAt: string | null;
  autoSubmitted: boolean;
  timeLimitSeconds: number;
  scoreCorrect: number | null;
  scoreTotal: number;
  contentVersion: string;
  level: TestLevel;
}

export interface Attempt extends AttemptSummary {
  questionIds: string[];
  answers: Partial<Record<string, OptionKey>>;
  /** Server clock at the time of the response, for countdown offset. */
  serverNow: string;
}

export interface AttemptStart {
  attemptId: string;
  questionIds: string[];
  startedAt: string;
  deadlineAt: string;
  serverNow: string;
}

export interface PerQuestionResult {
  id: string;
  given: OptionKey | null;
  correct: OptionKey;
  isCorrect: boolean;
}

export interface ScoreResult {
  attemptId: string;
  scoreCorrect: number;
  scoreTotal: number;
  autoSubmitted: boolean;
  submittedAt: string;
  perQuestion: PerQuestionResult[];
}

export interface BankTooSmall {
  error: 'bank_too_small';
  have: number;
  need: number;
}

// ---------------------------------------------------------------- grading

export type GradeStatus = 'queued' | 'running' | 'passed' | 'failed' | 'error';

export interface GradeTest {
  test: string;
  outcome: string;
  /** The assertion or exception message: what was observed. */
  message?: string;
  /** The check's docstring: what it wants and why, written for the learner. */
  expects?: string;
}

/** What grading/<SEC>/grade.py returns through dbutils.notebook.exit. */
export interface GradeResult {
  section: string;
  passed: boolean;
  total: number;
  failed: GradeTest[];
  tests: { test: string; outcome: string }[];
  report_tail: string;
}

export interface GradingRun {
  id: string;
  sectionId: string;
  runId: number | null;
  status: GradeStatus;
  startedAt: string;
  finishedAt: string | null;
  result: GradeResult | null;
  error: string | null;
}

// ---------------------------------------------------------------- assignments

export interface Starter {
  name: string;
  source: string;
}

export interface AssignmentGate {
  ready: boolean;
  done: number;
  total: number;
  missing: string[];
}

/** The learner's own copy of a section's starter notebooks. */
export interface AssignmentState {
  sectionId: string;
  hasStarters: boolean;
  provisioned: boolean;
  /** Workspace path of the folder holding the copy, e.g. /Users/<app-sp>/learners/<email>/ASSOC-S3. */
  folder: string | null;
  /** Workspace path of the main notebook to open. */
  notebook: string | null;
  resetCount: number;
  /** A reset job is still dropping the section's output tables. */
  resetting: boolean;
  gate: AssignmentGate;
}

export interface ResetAllResult {
  exam: ExamId;
  sections: string[];
  runId: number | null;
}
