/**
 * Typed access to the generated content bundle.
 *
 * The JSON files next to this module are written by tools/build_app_content.py
 * and committed. Regenerate them after editing anything under content/ or
 * notebooks/; `python3 tools/build_app_content.py --check` is what CI runs.
 */

import examsJson from './exams.json' with { type: 'json' };
import questionsJson from './questions.json' with { type: 'json' };
import notesJson from './notes.json' with { type: 'json' };
import notebooksJson from './notebooks.json' with { type: 'json' };
import startersJson from './starters.json' with { type: 'json' };
import metaJson from './meta.json' with { type: 'json' };

import type {
  ContentMeta,
  Exam,
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
export const meta: ContentMeta = metaJson as ContentMeta;

const examIndex = new Map<ExamId, Exam>(exams.map((e) => [e.id, e]));
const questionIndex = new Map<string, Question>(questions.map((q) => [q.id, q]));
const sectionIndex = new Map<string, SectionSummary>(
  exams.flatMap((e) => e.sections.map((s) => [s.id, s] as const)),
);

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

/** Repo-relative paths of a section's lesson notebooks, in order. */
export function lessonPaths(sectionId: string): string[] {
  return (notebooks[sectionId]?.lessons ?? []).map((l) => l.path);
}
