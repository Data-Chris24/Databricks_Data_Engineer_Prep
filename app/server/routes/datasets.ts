import type { Application } from 'express';

import { notebooks } from '../../shared/content';
import { type DatasetRunRow, fromRow, settleRun } from '../../shared/datasets';
import type { DatasetState } from '../../shared/types';
import type { AppKitLike, Db, JobHandle } from '../lib/appkit';
import { isTerminal } from '../lib/grading';
import { currentUser, param, wrap } from '../lib/http';

/**
 * Section data on demand. One dispatcher job (`generate_datasets`, parameter
 * `section`) generates any section's teach and assess data; the app starts
 * it the first time a learner opens a section and records the run per
 * section, workspace-wide. See shared/datasets.ts for the rules.
 */
const COLS = 'section_id, run_id, status, started_by, started_at, finished_at, error';

function toRow(r: Record<string, unknown>): DatasetRunRow {
  const ts = (v: unknown) => (v instanceof Date ? v.toISOString() : typeof v === 'string' && v ? v : null);
  return {
    sectionId: String(r.section_id),
    runId: Number(r.run_id),
    status: String(r.status) as DatasetRunRow['status'],
    startedAt: ts(r.started_at) ?? new Date(0).toISOString(),
    finishedAt: ts(r.finished_at),
    error: (r.error as string | null) ?? null,
  };
}

export function registerDatasetRoutes(app: Application, db: Db, appkit: AppKitLike) {
  function handle(): JobHandle | null {
    try {
      return appkit.jobs ? appkit.jobs('generate_datasets') : null;
    } catch {
      return null;
    }
  }

  /** The recorded run, brought up to date with the job when still active. */
  async function state(sectionId: string): Promise<DatasetState> {
    const job = handle();
    const { rows } = await db.query(`SELECT ${COLS} FROM study.dataset_runs WHERE section_id = $1`, [sectionId]);
    if (!rows[0]) return fromRow(sectionId, null, job !== null);
    let row = toRow(rows[0]);
    if ((row.status === 'queued' || row.status === 'running') && job) {
      const run = await job.getRun(row.runId);
      if (run.ok) {
        if (isTerminal(run.data)) {
          const settled = settleRun(run.data.state?.result_state, run.data.state?.state_message);
          const upd = await db.query(
            `UPDATE study.dataset_runs SET status = $2, error = $3, finished_at = now() WHERE section_id = $1 RETURNING ${COLS}`,
            [sectionId, settled.status, settled.error],
          );
          row = toRow(upd.rows[0]);
        } else if (row.status === 'queued' && run.data.state?.life_cycle_state === 'RUNNING') {
          await db.query("UPDATE study.dataset_runs SET status = 'running' WHERE section_id = $1", [sectionId]);
          row = { ...row, status: 'running' };
        }
      }
    }
    return fromRow(sectionId, row, job !== null);
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
      const current = await state(sectionId);
      const job = handle();
      if (current.status === 'unconfigured' || !job) {
        res.status(503).json({ error: 'datasets_not_configured', state: current });
        return;
      }
      if (current.status === 'preparing' || (current.status === 'ready' && !force)) {
        res.json(current);
        return;
      }
      const started = await job.runNow({ job_parameters: { section: sectionId } });
      if (!started.ok) {
        const msg = typeof started.error === 'string' ? started.error : (started.error as { message?: string }).message ?? 'could not start the generate job';
        res.status(502).json({ error: 'datasets_start_failed', message: msg.slice(0, 500), state: current });
        return;
      }
      const { rows } = await db.query(
        `INSERT INTO study.dataset_runs (section_id, run_id, status, started_by)
         VALUES ($1, $2, 'queued', $3)
         ON CONFLICT (section_id) DO UPDATE SET
           run_id = EXCLUDED.run_id, status = 'queued', started_by = EXCLUDED.started_by,
           started_at = now(), finished_at = NULL, error = NULL
         RETURNING ${COLS}`,
        [sectionId, started.data.run_id, currentUser(res).userId],
      );
      res.json(fromRow(sectionId, toRow(rows[0])));
    }),
  );
}
