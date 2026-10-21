import type { Db, JobHandle } from './appkit';

/**
 * Free Edition disables a Lakebase endpoint after a few days without a
 * connection, and it stays off until someone who manages the project turns it
 * back on. Every query then fails with "The endpoint has been disabled". The
 * app's principal can only connect, so it runs the "[DE prep] Wake the study
 * database" job, which runs as the deployer (ops/wake_database.py), and tells
 * the learner to wait instead of answering a bare 500.
 */

const DISABLED = /endpoint has been disabled/i;

export function isEndpointDisabled(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return DISABLED.test(msg);
}

/** A query failed because the database is off; a wake has been asked for. */
export class DatabaseAsleepError extends Error {
  constructor(readonly waking: boolean) {
    super(waking ? 'The study database is waking up' : 'The study database is disabled and no wake job is configured');
  }
}

const TERMINAL = new Set(['TERMINATED', 'SKIPPED', 'INTERNAL_ERROR']);

export interface Waker {
  /** Start a wake run unless one is already going. True when a run is (now) in flight. */
  wake(): Promise<boolean>;
}

/**
 * At most one wake run at a time, however many requests hit the disabled
 * database. A finished run is not trusted to have worked: if queries still
 * fail, the next one starts another run.
 */
export function createWaker(job: () => JobHandle | null, log: (msg: string) => void = console.log): Waker {
  let runId: number | null = null;
  let pending: Promise<boolean> | null = null;

  async function inFlight(): Promise<boolean> {
    if (runId === null) return false;
    const got = await job()?.getRun(runId);
    const state = got?.ok ? got.data.state?.life_cycle_state : undefined;
    // Unknown counts as running: better to wait than to stack up runs.
    return !state || !TERMINAL.has(state);
  }

  async function start(): Promise<boolean> {
    const handle = job();
    if (!handle) return false;
    if (await inFlight()) return true;
    const res = await handle.runNow();
    if (!res.ok) {
      log(`[db] could not start the wake job: ${typeof res.error === 'string' ? res.error : res.error.message}`);
      return false;
    }
    runId = res.data.run_id;
    log(`[db] endpoint is disabled; started wake run ${runId}`);
    return true;
  }

  return {
    wake() {
      pending ??= start()
        .catch((err: unknown) => {
          log(`[db] wake failed: ${err instanceof Error ? err.message : String(err)}`);
          return false;
        })
        .finally(() => {
          pending = null;
        });
      return pending;
    },
  };
}

/** The same database, but a "disabled" failure starts a wake and becomes a DatabaseAsleepError. */
export function wakingDb(db: Db, waker: Waker): Db {
  return {
    async query(text, params) {
      try {
        return await db.query(text, params);
      } catch (err) {
        if (!isEndpointDisabled(err)) throw err;
        throw new DatabaseAsleepError(await waker.wake());
      }
    },
  };
}
