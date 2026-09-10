import type { Application } from 'express';

import { examById, sectionById } from '../../shared/content';
import type { GradeResult, GradeStatus, GradingRun } from '../../shared/types';
import type { AppKitLike, Db, JobHandle } from '../lib/appkit';
import { gradeJobKey, isTerminal, settle, taskRunId } from '../lib/grading';
import { currentUser, iso, num, param, wrap } from '../lib/http';

const COLS = 'id, section_id, run_id, status, started_at, finished_at, result, error';

export function toGradingRun(r: Record<string, unknown>): GradingRun {
  return {
    id: String(r.id),
    sectionId: String(r.section_id),
    runId: r.run_id === null || r.run_id === undefined ? null : num(r.run_id),
    status: r.status as GradeStatus,
    startedAt: iso(r.started_at) ?? '',
    finishedAt: iso(r.finished_at),
    result: (r.result as GradeResult | null) ?? null,
    error: (r.error as string | null) ?? null,
  };
}

function handleFor(appkit: AppKitLike, sectionId: string): JobHandle | null {
  if (!appkit.jobs) return null;
  try {
    return appkit.jobs(gradeJobKey(sectionId));
  } catch {
    return null;
  }
}

export function registerGradingRoutes(app: Application, db: Db, appkit: AppKitLike) {
  /** Bring a queued/running row up to date with the job run. */
  async function refresh(row: Record<string, unknown>): Promise<Record<string, unknown>> {
    const status = String(row.status);
    if (status !== 'queued' && status !== 'running') return row;
    const runId = row.run_id === null ? null : num(row.run_id);
    const handle = handleFor(appkit, String(row.section_id));
    if (runId === null || !handle) return row;

    const run = await handle.getRun(runId);
    if (!run.ok) return row;
    if (!isTerminal(run.data)) {
      if (status === 'queued') {
        await db.query("UPDATE study.grading_runs SET status = 'running' WHERE id = $1", [row.id]);
        return { ...row, status: 'running' };
      }
      return row;
    }
    const output = await handle.getRunOutput(taskRunId(run.data, runId));
    const settled = settle(run.data, output.ok ? output.data : null);
    const { rows } = await db.query(
      `UPDATE study.grading_runs
          SET status = $2, result = $3::jsonb, error = $4, finished_at = now()
        WHERE id = $1 RETURNING ${COLS}`,
      [row.id, settled.status, settled.result ? JSON.stringify(settled.result) : null, settled.error],
    );
    return rows[0] ?? row;
  }

  async function latest(userId: string, sectionId: string) {
    const { rows } = await db.query(
      `SELECT ${COLS} FROM study.grading_runs WHERE user_id = $1 AND section_id = $2
        ORDER BY started_at DESC LIMIT 1`,
      [userId, sectionId],
    );
    return rows[0];
  }

  app.get(
    '/api/grading/exam/:exam',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      if (!exam) {
        res.status(404).json({ error: 'unknown_exam' });
        return;
      }
      const user = currentUser(res);
      const { rows } = await db.query(
        `SELECT DISTINCT ON (section_id) ${COLS} FROM study.grading_runs
          WHERE user_id = $1 ORDER BY section_id, started_at DESC`,
        [user.userId],
      );
      const out: Record<string, GradingRun> = {};
      for (const r of rows) {
        const sid = String(r.section_id);
        if (exam.sections.some((s) => s.id === sid)) out[sid] = toGradingRun(await refresh(r));
      }
      res.json(out);
    }),
  );

  app.get(
    '/api/grading/section/:sectionId',
    wrap(async (req, res) => {
      const section = sectionById(param(req, 'sectionId'));
      if (!section) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      const user = currentUser(res);
      const row = await latest(user.userId, section.id);
      res.json({ run: row ? toGradingRun(await refresh(row)) : null, configured: handleFor(appkit, section.id) !== null });
    }),
  );

  app.post(
    '/api/grading/section/:sectionId/run',
    wrap(async (req, res) => {
      const section = sectionById(param(req, 'sectionId'));
      if (!section) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      const user = currentUser(res);
      const handle = handleFor(appkit, section.id);
      if (!handle) {
        res.status(503).json({ error: 'grading_not_configured' });
        return;
      }
      const current = await latest(user.userId, section.id);
      if (current) {
        const fresh = await refresh(current);
        if (fresh.status === 'queued' || fresh.status === 'running') {
          res.status(409).json({ error: 'grading_in_progress', run: toGradingRun(fresh) });
          return;
        }
      }
      const started = await handle.runNow({});
      if (!started.ok) {
        const msg = typeof started.error === 'string' ? started.error : (started.error as { message?: string }).message ?? 'could not start the grading job';
        const { rows } = await db.query(
          `INSERT INTO study.grading_runs (user_id, section_id, status, error, finished_at)
             VALUES ($1, $2, 'error', $3, now()) RETURNING ${COLS}`,
          [user.userId, section.id, msg.slice(0, 2000)],
        );
        res.status(502).json({ error: 'grading_start_failed', run: toGradingRun(rows[0]) });
        return;
      }
      const { rows } = await db.query(
        `INSERT INTO study.grading_runs (user_id, section_id, run_id, status)
           VALUES ($1, $2, $3, 'queued') RETURNING ${COLS}`,
        [user.userId, section.id, started.data.run_id],
      );
      res.status(201).json(toGradingRun(rows[0]));
    }),
  );
}
