import type { DatasetState } from './types';

/**
 * A section's data is prepared by one dispatcher job (`generate_datasets`,
 * parameter `section`) that the app starts the first time a learner opens a
 * section. The app records the run it started per section, workspace-wide,
 * and settles it against the job: a successful run means the data is there,
 * an active one means it is being made, a failed one is shown with its
 * message and a retry. Data generated from a terminal before the app existed
 * is not visible here, so such a section is generated once more on first
 * open; the generators overwrite, so that is safe.
 */
export interface DatasetRunRow {
  sectionId: string;
  runId: number;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  startedAt: string;
  finishedAt: string | null;
  error: string | null;
}

export function fromRow(sectionId: string, row: DatasetRunRow | null, configured = true): DatasetState {
  const blank: DatasetState = { sectionId, status: 'missing', runId: null, startedAt: null, finishedAt: null, error: null };
  if (!configured) return { ...blank, status: 'unconfigured' };
  if (!row) return blank;
  const status = row.status === 'succeeded' ? 'ready' : row.status === 'failed' ? 'failed' : 'preparing';
  return { sectionId, status, runId: row.runId, startedAt: row.startedAt, finishedAt: row.finishedAt, error: row.error };
}

/** What a terminal job run means for the recorded row. */
export function settleRun(resultState: string | null | undefined, message: string | null | undefined): { status: 'succeeded' | 'failed'; error: string | null } {
  if (resultState === 'SUCCESS') return { status: 'succeeded', error: null };
  return { status: 'failed', error: (message?.trim() || resultState || 'the generate job failed').slice(0, 500) };
}
