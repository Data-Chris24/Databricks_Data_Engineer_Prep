import { createWorkspaceClient } from '@databricks/appkit';
import type { Application } from 'express';

import { notebooks } from '../../shared/content';
import { datasetStatus, type RunSummary } from '../../shared/datasets';
import type { DatasetState } from '../../shared/types';
import type { AppKitLike } from '../lib/appkit';
import { param, wrap } from '../lib/http';

/**
 * Section data on demand. Each section has a bundle job that generates its
 * teach and assess datasets; the app reads that job's run history to decide
 * whether the data exists (any successful run) or is being made (an active
 * run), and starts the job when it has never run. The section page calls
 * `prepare` on its own the first time a learner opens a section, so nobody
 * has to leave the browser.
 */
const CACHE_MS = 20_000;

export function registerDatasetRoutes(app: Application, appkit: AppKitLike) {
  const cache = new Map<string, { at: number; state: DatasetState }>();

  function jobKey(sectionId: string): string | null {
    return notebooks[sectionId]?.datasets.job ?? null;
  }
  function jobId(key: string): number | null {
    const raw = process.env[`DATABRICKS_JOB_${key.toUpperCase()}`];
    const n = raw ? Number(raw) : NaN;
    return Number.isFinite(n) ? n : null;
  }

  async function listRuns(id: number): Promise<RunSummary[]> {
    const ws = createWorkspaceClient().toLegacyWorkspaceClient();
    const out: RunSummary[] = [];
    for await (const r of ws.jobs.listRuns({ job_id: id, limit: 25 })) {
      if (r.run_id === undefined) continue;
      out.push({
        runId: r.run_id,
        lifeCycle: String(r.state?.life_cycle_state ?? ''),
        result: r.state?.result_state ? String(r.state.result_state) : null,
        message: r.state?.state_message ?? null,
        startTime: r.start_time ?? null,
        endTime: r.end_time ?? null,
      });
      if (out.length >= 25) break;
    }
    return out;
  }

  async function state(sectionId: string, fresh = false): Promise<DatasetState> {
    const key = jobKey(sectionId);
    const id = key ? jobId(key) : null;
    if (!key || id === null) return datasetStatus(sectionId, [], false);
    const hit = cache.get(sectionId);
    if (!fresh && hit && Date.now() - hit.at < CACHE_MS) return hit.state;
    const s = datasetStatus(sectionId, await listRuns(id));
    cache.set(sectionId, { at: Date.now(), state: s });
    return s;
  }

  app.get(
    '/api/datasets/:sectionId',
    wrap(async (req, res) => {
      const sectionId = param(req, 'sectionId');
      if (!notebooks[sectionId]) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      res.json(await state(sectionId));
    }),
  );

  /** Start the generate job unless the data is ready or being made; `force` regenerates. */
  app.post(
    '/api/datasets/:sectionId/prepare',
    wrap(async (req, res) => {
      const sectionId = param(req, 'sectionId');
      if (!notebooks[sectionId]) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      const force = (req.body as { force?: boolean } | undefined)?.force === true;
      const current = await state(sectionId, true);
      if (current.status === 'unconfigured') {
        res.status(503).json({ error: 'datasets_not_configured', state: current });
        return;
      }
      if (current.status === 'preparing' || (current.status === 'ready' && !force)) {
        res.json(current);
        return;
      }
      const key = jobKey(sectionId);
      let handle;
      try {
        handle = key && appkit.jobs ? appkit.jobs(key) : null;
      } catch {
        handle = null;
      }
      if (!handle) {
        res.status(503).json({ error: 'datasets_not_configured', state: current });
        return;
      }
      const started = await handle.runNow();
      if (!started.ok) {
        const msg = typeof started.error === 'string' ? started.error : (started.error as { message?: string }).message ?? 'could not start the generate job';
        res.status(502).json({ error: 'datasets_start_failed', message: msg.slice(0, 500), state: current });
        return;
      }
      cache.delete(sectionId);
      const next: DatasetState = { sectionId, status: 'preparing', runId: started.data.run_id, startedAt: new Date().toISOString(), finishedAt: null, error: null };
      cache.set(sectionId, { at: Date.now(), state: next });
      res.json(next);
    }),
  );
}
