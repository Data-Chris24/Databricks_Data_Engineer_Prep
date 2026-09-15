import type { DatasetState, DatasetStatus } from './types';

/**
 * A section's data is "ready" when its generate job has ever succeeded in
 * this workspace. The job history is the source of truth: it is what a
 * `databricks bundle run generate_datasets_<section>` leaves behind too, so
 * data generated from a terminal counts, and the app can read it with the
 * run permission the bundle grants (no Unity Catalog probing by the app's own
 * principal, which has no grants there).
 */
export interface RunSummary {
  runId: number;
  lifeCycle: string;
  result: string | null;
  message: string | null;
  startTime: number | null;
  endTime: number | null;
}

const ACTIVE = new Set(['PENDING', 'QUEUED', 'RUNNING', 'TERMINATING', 'BLOCKED', 'WAITING']);

const iso = (ms: number | null) => (ms ? new Date(ms).toISOString() : null);

export function datasetStatus(sectionId: string, runs: RunSummary[], configured = true): DatasetState {
  const blank: DatasetState = { sectionId, status: 'missing', runId: null, startedAt: null, finishedAt: null, error: null };
  if (!configured) return { ...blank, status: 'unconfigured' as DatasetStatus };
  const byStart = [...runs].sort((a, b) => (b.startTime ?? 0) - (a.startTime ?? 0));
  const active = byStart.find((r) => ACTIVE.has(r.lifeCycle));
  if (active) return { ...blank, status: 'preparing', runId: active.runId, startedAt: iso(active.startTime) };
  const success = byStart.find((r) => r.result === 'SUCCESS');
  if (success) return { ...blank, status: 'ready', runId: success.runId, startedAt: iso(success.startTime), finishedAt: iso(success.endTime) };
  const failed = byStart.find((r) => !ACTIVE.has(r.lifeCycle));
  if (failed) {
    return { ...blank, status: 'failed', runId: failed.runId, startedAt: iso(failed.startTime), finishedAt: iso(failed.endTime), error: failed.message ?? failed.result ?? 'the generate job failed' };
  }
  return blank;
}
