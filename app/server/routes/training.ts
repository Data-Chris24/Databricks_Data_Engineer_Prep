import type { Application } from 'express';
import { z } from 'zod';

import { examById, lessonPaths, notebooks, sectionById } from '../../shared/content';
import type { ProgressRow, TrainingState } from '../../shared/types';
import type { Db } from '../lib/appkit';
import { currentUser, iso, num, param, parseBody, wrap } from '../lib/http';

const Visit = z.object({ path: z.string().min(1).max(300) });

function examLessonPaths(examId: string): string[] {
  const exam = examById(examId);
  return exam ? exam.sections.flatMap((s) => lessonPaths(s.id)) : [];
}

const Patch = z.object({
  anchor: z.string().max(200).optional(),
  scrollPct: z.number().int().min(0).max(100).optional(),
  completed: z.boolean().optional(),
});

export function toProgressRow(r: Record<string, unknown>): ProgressRow {
  return {
    sectionId: String(r.section_id),
    visited: Boolean(r.visited),
    completed: Boolean(r.completed),
    completedAt: iso(r.completed_at),
    lastAnchor: (r.last_anchor as string | null) ?? null,
    scrollPct: r.scroll_pct === null || r.scroll_pct === undefined ? null : num(r.scroll_pct),
    lastSeen: iso(r.last_seen) ?? new Date(0).toISOString(),
  };
}

export function registerTrainingRoutes(app: Application, db: Db) {
  app.get(
    '/api/training/:exam',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      if (!exam) {
        res.status(404).json({ error: 'unknown_exam' });
        return;
      }
      const user = currentUser(res);
      const { rows } = await db.query(
        `SELECT section_id, visited, completed, completed_at, last_anchor, scroll_pct, last_seen
           FROM study.training_progress
          WHERE user_id = $1 AND exam = $2
          ORDER BY last_seen DESC`,
        [user.userId, exam.id],
      );
      const sections: Record<string, ProgressRow> = {};
      for (const r of rows) {
        const p = toProgressRow(r);
        sections[p.sectionId] = p;
      }
      const latest = rows[0] ? toProgressRow(rows[0]) : null;
      const completed = Object.values(sections).filter((s) => s.completed).length;
      const paths = examLessonPaths(exam.id);
      const { rows: visits } = paths.length
        ? await db.query('SELECT path FROM study.notebook_visits WHERE user_id = $1 AND path = ANY($2::text[])', [user.userId, paths])
        : { rows: [] };
      const body: TrainingState = {
        sections,
        resume: latest ? { sectionId: latest.sectionId, anchor: latest.lastAnchor } : null,
        percentComplete: Math.round((completed / exam.sections.length) * 100),
        visited: visits.map((v) => String(v.path)),
      };
      res.json(body);
    }),
  );

  app.put(
    '/api/training/:exam/sections/:sectionId',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      const section = sectionById(param(req, 'sectionId'));
      if (!exam || !section || !exam.sections.some((s) => s.id === section.id)) {
        res.status(404).json({ error: 'unknown_section' });
        return;
      }
      const body = parseBody(Patch, req, res);
      if (!body) return;
      const user = currentUser(res);
      const { rows } = await db.query(
        `INSERT INTO study.training_progress
           (user_id, exam, section_id, last_anchor, scroll_pct, completed, completed_at)
         VALUES ($1, $2, $3, $4, $5, COALESCE($6, false),
                 CASE WHEN $6 THEN now() ELSE NULL END)
         ON CONFLICT (user_id, section_id) DO UPDATE SET
           last_anchor  = COALESCE(EXCLUDED.last_anchor, study.training_progress.last_anchor),
           scroll_pct   = COALESCE(EXCLUDED.scroll_pct, study.training_progress.scroll_pct),
           completed    = COALESCE($6, study.training_progress.completed),
           completed_at = CASE
                            WHEN $6 IS TRUE AND study.training_progress.completed_at IS NULL THEN now()
                            WHEN $6 IS FALSE THEN NULL
                            ELSE study.training_progress.completed_at
                          END,
           visited      = true,
           last_seen    = now()
         RETURNING section_id, visited, completed, completed_at, last_anchor, scroll_pct, last_seen`,
        [
          user.userId,
          exam.id,
          section.id,
          body.anchor ?? null,
          body.scrollPct ?? null,
          body.completed ?? null,
        ],
      );
      res.json(toProgressRow(rows[0]));
    }),
  );

  app.post(
    '/api/training/:exam/reset',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      if (!exam) {
        res.status(404).json({ error: 'unknown_exam' });
        return;
      }
      const user = currentUser(res);
      await db.query('DELETE FROM study.training_progress WHERE user_id = $1 AND exam = $2', [
        user.userId,
        exam.id,
      ]);
      const paths = examLessonPaths(exam.id);
      if (paths.length) {
        await db.query('DELETE FROM study.notebook_visits WHERE user_id = $1 AND path = ANY($2::text[])', [user.userId, paths]);
      }
      res.status(204).end();
    }),
  );

  app.put(
    '/api/training/visits',
    wrap(async (req, res) => {
      const body = parseBody(Visit, req, res);
      if (!body) return;
      const known = Object.values(notebooks).some((n) => n.lessons.some((l) => l.path === body.path));
      if (!known) {
        res.status(404).json({ error: 'unknown_notebook' });
        return;
      }
      const user = currentUser(res);
      await db.query(
        `INSERT INTO study.notebook_visits (user_id, path) VALUES ($1, $2)
         ON CONFLICT (user_id, path) DO UPDATE SET last_at = now()`,
        [user.userId, body.path],
      );
      res.status(204).end();
    }),
  );
}
