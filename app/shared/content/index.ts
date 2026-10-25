/**
 * Typed access to the generated content bundle.
 *
 * The JSON files next to this module are written by tools/build_app_content.py
 * and are not committed (gitignored). `npm run dev`, `npm test` and
 * `npm run typecheck` build them first; CI and deploy.yml build them too.
 * After editing content/ or notebooks/ while the dev server runs, re-run
 * `npm run content`.
 */

import examsJson from './exams.json' with { type: 'json' };
import questionsJson from './questions.json' with { type: 'json' };
import notesJson from './notes.json' with { type: 'json' };
import notebooksJson from './notebooks.json' with { type: 'json' };
import startersJson from './starters.json' with { type: 'json' };
import visualsJson from './visuals.json' with { type: 'json' };
import metaJson from './meta.json' with { type: 'json' };

import type {
  ContentMeta,
  Exam,
  ExtraAssignment,
  ExamId,
  Question,
  SectionNote,
  SectionNotebooks,
  SectionSummary,
  Starter,
} from '../types';

// The JSON is produced by a script whose output shape the Python tests pin,
// so these are honest annotations rather than runtime validation.
export const exams: Exam[] = examsJson as Exam[];
export const questions: Question[] = questionsJson as Question[];
export const notes: Record<string, SectionNote> = notesJson as Record<string, SectionNote>;
export const notebooks: Record<string, SectionNotebooks> = notebooksJson as Record<
  string,
  SectionNotebooks
>;
export const starters: Record<string, Starter[]> = startersJson as Record<string, Starter[]>;
/** Interactive diagrams (content/visuals/*.html), keyed by name; notes embed them as `visual:<name>`. */
export const visuals: Record<string, string> = visualsJson as Record<string, string>;
export const meta: ContentMeta = metaJson as ContentMeta;

const examIndex = new Map<ExamId, Exam>(exams.map((e) => [e.id, e]));
const questionIndex = new Map<string, Question>(questions.map((q) => [q.id, q]));
const sectionIndex = new Map<string, SectionSummary>(exams.flatMap((e) => e.sections.map((s) => [s.id, s] as const)));

export function examById(id: string): Exam | undefined {
  return examIndex.get(id as ExamId);
}

export function isExamId(id: string): id is ExamId {
  return examIndex.has(id as ExamId);
}

export function questionById(id: string): Question | undefined {
  return questionIndex.get(id);
}

export function sectionById(id: string): SectionSummary | undefined {
  return sectionIndex.get(id);
}

export function questionsFor(exam: ExamId, section?: string): Question[] {
  return questions.filter((q) => q.exam === exam && (!section || q.section === section));
}

/** Distinct families (a question plus its variants) available for an exam. */
export function familiesFor(exam: ExamId): number {
  return new Set(questionsFor(exam).map((q) => q.family)).size;
}

/** Repo-relative paths of a section's required lesson notebooks, in order: the assignment gate. */
export function lessonPaths(sectionId: string): string[] {
  return (notebooks[sectionId]?.lessons ?? []).filter((l) => !l.optional).map((l) => l.path);
}

/** Every lesson notebook of a section, optional ones included. */
export function allLessonPaths(sectionId: string): string[] {
  return (notebooks[sectionId]?.lessons ?? []).map((l) => l.path);
}

/**
 * An assignment the app can provision, grade and reset: a section's own (its id
 * is the section id) or an optional extra beside it.
 */
export interface AssignmentRef {
  id: string;
  sectionId: string;
  /** Lesson paths that must have been opened before it unlocks. */
  gate: string[];
  extra: ExtraAssignment | null;
}

const extraIndex = new Map<string, { sectionId: string; extra: ExtraAssignment }>(
  Object.entries(notebooks).flatMap(([sid, nb]) => (nb.extras ?? []).map((x) => [x.id, { sectionId: sid, extra: x }] as const)),
);

export function assignmentById(id: string): AssignmentRef | undefined {
  const section = sectionIndex.get(id);
  if (section) return { id: section.id, sectionId: section.id, gate: lessonPaths(section.id), extra: null };
  const x = extraIndex.get(id);
  return x ? { id: x.extra.id, sectionId: x.sectionId, gate: x.extra.gate, extra: x.extra } : undefined;
}

/** A section's id followed by its extras' ids. */
export function assignmentIdsFor(sectionId: string): string[] {
  return [sectionId, ...(notebooks[sectionId]?.extras ?? []).map((x) => x.id)];
}
