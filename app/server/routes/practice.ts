import type { Application } from 'express';
import { z } from 'zod';

import { examById, questionById } from '../../shared/content';
import { schedule, type ReviewState } from '../../shared/sm2';
import type { Quality, ReviewRow } from '../../shared/types';
import type { Db } from '../lib/appkit';
import { asDate, currentUser, iso, num, param, parseBody, wrap } from '../lib/http';

const Rate = z.object({
  questionId: z.string().min(1),
  quality: z.union([z.literal(0), z.literal(1), z.literal(2), z.literal(3)]),
});

export function toReviewRow(r: Record<string, unknown>): ReviewRow {
  return {
    questionId: String(r.question_id),
    n: num(r.n),
    ease: num(r.ease),
    dueAt: iso(r.due_at),
    lastRatedAt: iso(r.last_rated_at),
    lastQuality: r.last_quality === null || r.last_quality === undefined ? null : num(r.last_quality),
    rightCount: num(r.right_count),
    wrongCount: num(r.wrong_count),
  };
}

function toState(r: Record<string, unknown> | undefined): ReviewState | null {
  if (!r) return null;
  return {
    n: num(r.n),
    ease: num(r.ease),
    dueAt: asDate(r.due_at)?.getTime() ?? null,
    lastRatedAt: asDate(r.last_rated_at)?.getTime() ?? null,
    lastQuality: (r.last_quality === null ? null : (num(r.last_quality) as Quality)) ?? null,
    rightCount: num(r.right_count),
    wrongCount: num(r.wrong_count),
  };
}

export function registerPracticeRoutes(app: Application, db: Db) {
  app.get(
    '/api/practice/:exam/state',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      if (!exam) {
        res.status(404).json({ error: 'unknown_exam' });
        return;
      }
      const user = currentUser(res);
      const { rows } = await db.query('SELECT * FROM study.review_state WHERE user_id = $1', [
        user.userId,
      ]);
      const out: Record<string, ReviewRow> = {};
      for (const r of rows) {
        const q = questionById(String(r.question_id));
        if (q && q.exam === exam.id) out[q.id] = toReviewRow(r);
      }
      res.json(out);
    }),
  );

  app.post(
    '/api/practice/rate',
    wrap(async (req, res) => {
      const body = parseBody(Rate, req, res);
      if (!body) return;
      if (!questionById(body.questionId)) {
        res.status(404).json({ error: 'unknown_question' });
        return;
      }
      const user = currentUser(res);
      const { rows: existing } = await db.query(
        'SELECT * FROM study.review_state WHERE user_id = $1 AND question_id = $2',
        [user.userId, body.questionId],
      );
      const next = schedule(toState(existing[0]), body.quality);
      const { rows } = await db.query(
        `INSERT INTO study.review_state
           (user_id, question_id, n, ease, due_at, last_rated_at, last_quality, right_count, wrong_count)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         ON CONFLICT (user_id, question_id) DO UPDATE SET
           n = EXCLUDED.n, ease = EXCLUDED.ease, due_at = EXCLUDED.due_at,
           last_rated_at = EXCLUDED.last_rated_at, last_quality = EXCLUDED.last_quality,
           right_count = EXCLUDED.right_count, wrong_count = EXCLUDED.wrong_count
         RETURNING *`,
        [
          user.userId,
          body.questionId,
          next.n,
          next.ease,
          next.dueAt === null ? null : new Date(next.dueAt),
          next.lastRatedAt === null ? null : new Date(next.lastRatedAt),
          next.lastQuality,
          next.rightCount,
          next.wrongCount,
        ],
      );
      res.json(toReviewRow(rows[0]));
    }),
  );
}
