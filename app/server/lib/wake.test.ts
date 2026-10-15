import { describe, expect, it, vi } from 'vitest';

import type { Db, JobHandle } from './appkit';
import { createWaker, DatabaseAsleepError, isEndpointDisabled, wakingDb } from './wake';

const DISABLED = new Error('The endpoint has been disabled. Enable it using the Lakebase UI or API.');

function fakeJob(states: string[]) {
  let i = 0;
  const handle = {
    runNow: vi.fn(() => Promise.resolve({ ok: true as const, data: { run_id: 7 } })),
    getRun: vi.fn(() =>
      Promise.resolve({
        ok: true as const,
        data: { state: { life_cycle_state: states[Math.min(i++, states.length - 1)] } },
      }),
    ),
    getRunOutput: vi.fn(),
  };
  return handle as typeof handle & JobHandle;
}

const quiet = () => {};

describe('isEndpointDisabled', () => {
  it('recognises the Lakebase message and nothing else', () => {
    expect(isEndpointDisabled(DISABLED)).toBe(true);
    expect(isEndpointDisabled(new Error('relation "study.users" does not exist'))).toBe(false);
  });
});

describe('createWaker', () => {
  it('starts one run for many concurrent requests', async () => {
    const job = fakeJob(['RUNNING']);
    const waker = createWaker(() => job, quiet);
    const all = await Promise.all([waker.wake(), waker.wake(), waker.wake()]);
    expect(all).toEqual([true, true, true]);
    expect(job.runNow).toHaveBeenCalledTimes(1);
  });

  it('does not start another while the run is still going', async () => {
    const job = fakeJob(['RUNNING']);
    const waker = createWaker(() => job, quiet);
    await waker.wake();
    await waker.wake();
    expect(job.runNow).toHaveBeenCalledTimes(1);
  });

  it('starts again once the run has finished and the database is still off', async () => {
    const job = fakeJob(['TERMINATED']);
    const waker = createWaker(() => job, quiet);
    await waker.wake();
    await waker.wake();
    expect(job.runNow).toHaveBeenCalledTimes(2);
  });

  it('reports false when no wake job is configured', async () => {
    expect(await createWaker(() => null, quiet).wake()).toBe(false);
  });
});

describe('wakingDb', () => {
  it('turns a disabled endpoint into DatabaseAsleepError and wakes it', async () => {
    const job = fakeJob(['RUNNING']);
    const db: Db = { query: () => Promise.reject(DISABLED) };
    const err = await wakingDb(
      db,
      createWaker(() => job, quiet),
    )
      .query('SELECT 1')
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DatabaseAsleepError);
    expect((err as DatabaseAsleepError).waking).toBe(true);
    expect(job.runNow).toHaveBeenCalledTimes(1);
  });

  it('passes other errors and results through untouched', async () => {
    const job = fakeJob(['RUNNING']);
    const boom = new Error('syntax error');
    const failing = wakingDb(
      { query: () => Promise.reject(boom) },
      createWaker(() => job, quiet),
    );
    await expect(failing.query('SELEC 1')).rejects.toBe(boom);
    const ok = wakingDb(
      { query: () => Promise.resolve({ rows: [{ x: 1 }] }) },
      createWaker(() => job, quiet),
    );
    expect(await ok.query('SELECT 1')).toEqual({ rows: [{ x: 1 }] });
    expect(job.runNow).not.toHaveBeenCalled();
  });
});
