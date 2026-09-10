import type { GradeResult, GradeStatus } from '../../shared/types';
import type { JobRun, JobRunOutput } from './appkit';

/** Job key for a section's grader, matching the bundle's resource keys. */
export function gradeJobKey(sectionId: string): string {
  return `grade_${sectionId.toLowerCase().replace(/-/g, '_')}`;
}

export function isTerminal(run: JobRun): boolean {
  const s = run.state?.life_cycle_state ?? '';
  return ['TERMINATED', 'INTERNAL_ERROR', 'SKIPPED'].includes(s);
}

/** For a single-task job, output lives on the task run, not the job run. */
export function taskRunId(run: JobRun, fallback: number): number {
  return run.tasks?.[0]?.run_id ?? fallback;
}

export function parseGradeOutput(output: JobRunOutput): GradeResult | null {
  const raw = output.notebook_output?.result;
  if (!raw) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object') return null;
  const r = parsed as Partial<GradeResult>;
  if (typeof r.passed !== 'boolean' || typeof r.total !== 'number' || !Array.isArray(r.failed)) return null;
  return {
    section: String(r.section ?? ''),
    passed: r.passed,
    total: r.total,
    failed: r.failed.map((f) => ({ test: String(f.test), outcome: String(f.outcome), message: f.message ? String(f.message) : undefined })),
    tests: Array.isArray(r.tests) ? r.tests.map((t) => ({ test: String(t.test), outcome: String(t.outcome) })) : [],
    report_tail: String(r.report_tail ?? ''),
  };
}

/** Settle a finished run into a status and, when the grader spoke, its result. */
export function settle(run: JobRun, output: JobRunOutput | null): { status: GradeStatus; result: GradeResult | null; error: string | null } {
  const result = output ? parseGradeOutput(output) : null;
  if (result) return { status: result.passed ? 'passed' : 'failed', result, error: null };
  const message = output?.error ?? run.state?.state_message ?? `run ended with ${run.state?.result_state ?? run.state?.life_cycle_state ?? 'unknown state'}`;
  return { status: 'error', result: null, error: message.slice(0, 2000) };
}
