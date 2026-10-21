import type { Application } from 'express';

/**
 * The slice of the AppKit object our routes use. Typed structurally (as the
 * scaffold does) so route modules can be exercised in tests with a fake.
 */
export interface Db {
  query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
}

export type ExecutionResult<T> = { ok: true; data: T } | { ok: false; error: { message?: string } | Error | string };

export interface JobRunState {
  life_cycle_state?: string;
  result_state?: string;
  state_message?: string;
}

export interface JobRun {
  run_id?: number;
  state?: JobRunState;
  tasks?: { run_id?: number; task_key?: string; state?: JobRunState }[];
}

export interface JobRunOutput {
  notebook_output?: { result?: string; truncated?: boolean };
  error?: string;
  metadata?: JobRun;
}

/** The slice of an AppKit job handle the grading route uses. */
export interface JobHandle {
  runNow(params?: Record<string, unknown>): Promise<ExecutionResult<{ run_id: number }>>;
  getRun(runId: number): Promise<ExecutionResult<JobRun>>;
  getRunOutput(runId: number): Promise<ExecutionResult<JobRunOutput>>;
}

export interface AppKitLike {
  lakebase: Db;
  server: {
    extend(fn: (app: Application) => void): void;
  };
  /** Throws when the key is unknown (job not configured in this environment). */
  jobs?: (key: string) => JobHandle;
}
