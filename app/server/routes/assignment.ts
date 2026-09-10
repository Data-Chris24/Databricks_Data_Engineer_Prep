import type { Application } from 'express';

import { lessonPaths, sectionById, starters } from '../../shared/content';
import { assignmentGate } from '../../shared/gate';
import type { AssignmentState } from '../../shared/types';
import type { Db } from '../lib/appkit';
import { currentUser, num, param, wrap } from '../lib/http';
import type { LearnerWorkspace } from '../lib/workspace';

async function visitedPaths(db: Db, userId: string, paths: string[]): Promise<string[]> {
  if (!paths.length) return [];
  const { rows } = await db.query('SELECT path FROM study.notebook_visits WHERE user_id = $1 AND path = ANY($2::text[])', [userId, paths]);
  return rows.map((r) => String(r.path));
}

export function registerAssignmentRoutes(app: Application, db: Db, learners: LearnerWorkspace) {
  async function state(userId: string, sectionId: string): Promise<AssignmentState> {
    const lessons = lessonPaths(sectionId);
    const gate = assignmentGate(lessons, await visitedPaths(db, userId, lessons));
    const { rows } = await db.query(
      'SELECT folder, notebook, reset_count FROM study.assignment_copies WHERE user_id = $1 AND section_id = $2',
      [userId, sectionId],
    );
    const row = rows[0];
    return {
      sectionId,
      hasStarters: (starters[sectionId] ?? []).length > 0,
      provisioned: Boolean(row),
      folder: row ? String(row.folder) : null,
      notebook: row ? String(row.notebook) : null,
      resetCount: row ? num(row.reset_count) : 0,
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
    if (!s.hasStarters) return { status: 404, body: { error: 'no_starter' } };
    if (!s.gate.ready) return { status: 409, body: { error: 'lessons_unvisited', gate: s.gate } };
    if (reset && !s.provisioned) return { status: 409, body: { error: 'not_provisioned' } };
    if (!learners.root()) return { status: 503, body: { error: 'learner_workspace_not_configured' } };
    const { folder, notebook } = await learners.provision(userId, sectionId, starters[sectionId] ?? [], reset);
    await db.query(
      `INSERT INTO study.assignment_copies (user_id, section_id, folder, notebook, reset_count, last_reset_at)
         VALUES ($1, $2, $3, $4, 0, NULL)
       ON CONFLICT (user_id, section_id) DO UPDATE SET
         folder = EXCLUDED.folder, notebook = EXCLUDED.notebook,
         reset_count = study.assignment_copies.reset_count + CASE WHEN $5 THEN 1 ELSE 0 END,
         last_reset_at = CASE WHEN $5 THEN now() ELSE study.assignment_copies.last_reset_at END`,
      [userId, sectionId, folder, notebook, reset],
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
