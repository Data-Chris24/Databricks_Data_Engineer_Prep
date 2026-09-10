import type { Application } from 'express';

import { lessonPaths, sectionById, starters } from '../../shared/content';
import { assignmentGate } from '../../shared/gate';
import type { AssignmentState } from '../../shared/types';
import type { AppKitLike, Db, JobHandle } from '../lib/appkit';
import { isTerminal } from '../lib/grading';
import { currentUser, num, param, wrap } from '../lib/http';

const text = (v: unknown): string => (typeof v === 'string' ? v : '');
import type { LearnerWorkspace } from '../lib/workspace';

async function visitedPaths(db: Db, userId: string, paths: string[]): Promise<string[]> {
  if (!paths.length) return [];
  const { rows } = await db.query('SELECT path FROM study.notebook_visits WHERE user_id = $1 AND path = ANY($2::text[])', [userId, paths]);
  return rows.map((r) => String(r.path));
}

export function registerAssignmentRoutes(app: Application, db: Db, learners: LearnerWorkspace, appkit: AppKitLike) {
  function resetJob(): JobHandle | null {
    if (!appkit.jobs) return null;
    try {
      return appkit.jobs('reset_assignment');
    } catch {
      return null;
    }
  }

  async function resetting(runId: number | null): Promise<boolean> {
    const job = resetJob();
    if (runId === null || !job) return false;
    const run = await job.getRun(runId);
    return run.ok ? !isTerminal(run.data) : false;
  }

  async function state(userId: string, sectionId: string): Promise<AssignmentState> {
    const lessons = lessonPaths(sectionId);
    const gate = assignmentGate(lessons, await visitedPaths(db, userId, lessons));
    const { rows } = await db.query(
      'SELECT folder, notebook, reset_count, reset_run_id FROM study.assignment_copies WHERE user_id = $1 AND section_id = $2',
      [userId, sectionId],
    );
    const row = rows[0];
    const resetRunId = row && row.reset_run_id !== null && row.reset_run_id !== undefined ? num(row.reset_run_id) : null;
    return {
      sectionId,
      hasStarters: (starters[sectionId] ?? []).length > 0,
      provisioned: Boolean(row && text(row.notebook)),
      folder: row && text(row.folder) ? text(row.folder) : null,
      notebook: row && text(row.notebook) ? text(row.notebook) : null,
      resetCount: row ? num(row.reset_count) : 0,
      resetting: await resetting(resetRunId),
      gate,
    };
  }

  app.get(
    '/api/assignment/:sectionId',
    wrap(async (req, res) => {
      const section = sectionById(param(req, 'sectionId'));
      if (!section) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      res.json(await state(currentUser(res).userId, section.id));
    }),
  );

  async function provision(sectionId: string, userId: string, reset: boolean) {
    const s = await state(userId, sectionId);
    if (!s.gate.ready) return { status: 409, body: { error: 'lessons_unvisited', gate: s.gate } };
    if (!reset && !s.hasStarters) return { status: 404, body: { error: 'no_starter' } };
    if (reset && s.resetting) return { status: 409, body: { error: 'reset_in_progress' } };

    // The notebook copy: created on first setup, overwritten on reset.
    let folder = s.folder ?? '';
    let notebook = s.notebook ?? '';
    if (s.hasStarters) {
      if (!learners.root()) return { status: 503, body: { error: 'learner_workspace_not_configured' } };
      const made = await learners.provision(userId, sectionId, starters[sectionId] ?? [], reset);
      folder = made.folder;
      notebook = made.notebook;
    }

    // The tables: a reset drops what the section's contract names, as a job run
    // by the deploying principal, and forgets the grades earned on them.
    let resetRunId: number | null = null;
    if (reset) {
      const job = resetJob();
      if (!job) return { status: 503, body: { error: 'reset_job_not_configured' } };
      const started = await job.runNow({ job_parameters: { section: sectionId } });
      if (!started.ok) {
        const msg = typeof started.error === 'string' ? started.error : (started.error as { message?: string }).message ?? 'could not start the reset job';
        return { status: 502, body: { error: 'reset_start_failed', message: msg.slice(0, 500) } };
      }
      resetRunId = started.data.run_id;
      await db.query('DELETE FROM study.grading_runs WHERE user_id = $1 AND section_id = $2', [userId, sectionId]);
    }

    await db.query(
      `INSERT INTO study.assignment_copies (user_id, section_id, folder, notebook, reset_count, last_reset_at, reset_run_id)
         VALUES ($1, $2, $3, $4, CASE WHEN $5 THEN 1 ELSE 0 END, CASE WHEN $5 THEN now() ELSE NULL END, $6)
       ON CONFLICT (user_id, section_id) DO UPDATE SET
         folder = CASE WHEN EXCLUDED.folder <> '' THEN EXCLUDED.folder ELSE study.assignment_copies.folder END,
         notebook = CASE WHEN EXCLUDED.notebook <> '' THEN EXCLUDED.notebook ELSE study.assignment_copies.notebook END,
         reset_count = study.assignment_copies.reset_count + CASE WHEN $5 THEN 1 ELSE 0 END,
         last_reset_at = CASE WHEN $5 THEN now() ELSE study.assignment_copies.last_reset_at END,
         reset_run_id = CASE WHEN $5 THEN EXCLUDED.reset_run_id ELSE study.assignment_copies.reset_run_id END`,
      [userId, sectionId, folder, notebook, reset, resetRunId],
    );
    return { status: 200, body: await state(userId, sectionId) };
  }

  app.post(
    '/api/assignment/:sectionId/provision',
    wrap(async (req, res) => {
      const section = sectionById(param(req, 'sectionId'));
      if (!section) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      const r = await provision(section.id, currentUser(res).userId, false);
      res.status(r.status).json(r.body);
    }),
  );

  app.post(
    '/api/assignment/:sectionId/reset',
    wrap(async (req, res) => {
      const section = sectionById(param(req, 'sectionId'));
      if (!section) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      const r = await provision(section.id, currentUser(res).userId, true);
      res.status(r.status).json(r.body);
    }),
  );
}
