import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ApiStore,
  AppRestartingError,
  DatabaseDisabledError,
  DatabaseWakingError,
  databaseWaking,
  LessonsUnvisitedError,
  MemoryStore,
  parseJson,
} from './store';

describe('parseJson', () => {
  it('parses a JSON body and treats an empty body as no data', () => {
    expect(parseJson(200, '{"a":1}')).toEqual({ a: 1 });
    expect(parseJson(200, '')).toEqual({});
  });
  it('turns the platform start page into a readable error, not a JSON parse failure', () => {
    expect(() => parseJson(503, '<!DOCTYPE html><html>starting</html>')).toThrow(AppRestartingError);
    expect(() => parseJson(200, 'not json at all')).toThrow(AppRestartingError);
    try {
      parseJson(503, '<html/>');
    } catch (e) {
      expect((e as Error).message).toMatch(/restarting/);
    }
  });
});

describe('a database that is waking up', () => {
  const asleep = () => new Response(JSON.stringify({ error: 'database_waking' }), { status: 503 });
  const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('makes a read wait, shows the banner meanwhile, and answers once it is back', async () => {
    vi.useFakeTimers();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(asleep())
      .mockResolvedValueOnce(asleep())
      .mockResolvedValueOnce(ok({ sections: {} }));
    vi.stubGlobal('fetch', fetch);
    const pending = new ApiStore().training('associate');
    await vi.advanceTimersByTimeAsync(0);
    expect(databaseWaking.get()).toBe(true);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(await pending).toEqual({ sections: {} });
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(databaseWaking.get()).toBe(false);
  });

  it('does not repeat a write: it fails with a readable message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(asleep()));
    await expect(new ApiStore().resetTraining('associate')).rejects.toThrow(DatabaseWakingError);
  });

  it('says how to wake it by hand when the app could not', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: 'database_disabled' }), { status: 503 })),
    );
    const err = await new ApiStore().training('associate').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DatabaseDisabledError);
    expect((err as Error).message).toMatch(/Wake the study database/);
  });
});

describe('an optional extra assignment, in the in-memory store', () => {
  const lessons = (paths: string[]) => paths.map((p) => `notebooks/lessons/associate/S2/${p}`);
  const required = lessons(['01_copy_into', '02_auto_loader', '03_schema_evolution']);
  const deepDive = lessons(['04_optional_auto_loader_deep_dive'])[0];

  it("opens the section's assignment without the optional lesson, but not the extra", async () => {
    const store = new MemoryStore();
    for (const p of required) await store.visitNotebook(p);
    expect((await store.assignment('ASSOC-S2')).gate.ready).toBe(true);
    const extra = await store.assignment('ASSOC-S2-AUTO-LOADER');
    expect(extra.gate).toMatchObject({ ready: false, missing: [deepDive] });
    await expect(store.provisionAssignment('ASSOC-S2-AUTO-LOADER')).rejects.toBeInstanceOf(LessonsUnvisitedError);
  });

  it('gets its own copy once the deep dive has been opened', async () => {
    const store = new MemoryStore();
    for (const p of [...required, deepDive]) await store.visitNotebook(p);
    const extra = await store.provisionAssignment('ASSOC-S2-AUTO-LOADER');
    expect(extra.provisioned).toBe(true);
    expect(extra.notebook).toMatch(/\/ASSOC-S2-AUTO-LOADER\/assignment$/);
    expect((await store.assignment('ASSOC-S2')).provisioned).toBe(false);
  });
});
