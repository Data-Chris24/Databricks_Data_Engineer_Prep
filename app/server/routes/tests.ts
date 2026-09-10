import type { Application } from 'express';
import { z } from 'zod';

import { examById, meta, questionById, questions } from '../../shared/content';
import type {
  Attempt,
  AttemptStart,
  AttemptSummary,
  OptionKey,
  ScoreResult,
} from '../../shared/types';
import type { Db } from '../lib/appkit';
import { grade } from '../../shared/grading';
import { currentUser, iso, num, param, parseBody, wrap } from '../lib/http';
import { BankTooSmallError, sampleTest } from '../../shared/sampler';

/** Answers received this long after the deadline still count (network slack). */
const GRACE_MS = 5_000;

const Start = z.object({
  timeLimitSecondsOverride: z.number().int().min(60).optional(),
});
const Answer = z.object({
  questionId: z.string().min(1),
  key: z.enum(['A', 'B', 'C', 'D', 'E', 'F']),
});
const Submit = z.object({ auto: z.boolean().optional() });

const SUMMARY_COLS = `attempt_id, exam, started_at, deadline_at, submitted_at, auto_submitted,
  time_limit_seconds, score_correct, score_total, content_version`;

export function toSummary(r: Record<string, unknown>): AttemptSummary {
  return {
    attemptId: String(r.attempt_id),
    exam: r.exam as AttemptSummary['exam'],
    startedAt: iso(r.started_at) ?? '',
    deadlineAt: iso(r.deadline_at) ?? '',
    submittedAt: iso(r.submitted_at),
    autoSubmitted: Boolean(r.auto_submitted),
    timeLimitSeconds: num(r.time_limit_seconds),
    scoreCorrect: r.score_correct === null || r.score_correct === undefined ? null : num(r.score_correct),
    scoreTotal: num(r.score_total),
    contentVersion: String(r.content_version),
  };
}

function toAttempt(r: Record<string, unknown>, now: Date): Attempt {
  return {
    ...toSummary(r),
    questionIds: r.question_ids as string[],
    answers: (r.answers as Partial<Record<string, OptionKey>>) ?? {},
    serverNow: now.toISOString(),
  };
}

export function registerTestRoutes(app: Application, db: Db) {
  async function loadOwned(attemptId: string, userId: string) {
    const { rows } = await db.query(
      'SELECT * FROM study.test_attempts WHERE attempt_id = $1 AND user_id = $2',
      [attemptId, userId],
    );
    return rows[0];
  }

  async function submit(row: Record<string, unknown>, auto: boolean): Promise<ScoreResult> {
    const questionIds = row.question_ids as string[];
    const answers = (row.answers as Partial<Record<string, OptionKey>>) ?? {};
    const result = grade(questionIds, answers, questionById);
    const { rows } = await db.query(
      `UPDATE study.test_attempts
          SET submitted_at = now(), auto_submitted = $2, score_correct = $3, score_total = $4
        WHERE attempt_id = $1 AND submitted_at IS NULL
        RETURNING submitted_at, auto_submitted`,
      [row.attempt_id, auto, result.correct, result.total],
    );
    const updated = rows[0] ?? row;
    return {
      attemptId: String(row.attempt_id),
      scoreCorrect: result.correct,
      scoreTotal: result.total,
      autoSubmitted: Boolean(updated.auto_submitted),
      submittedAt: iso(updated.submitted_at) ?? new Date().toISOString(),
      perQuestion: result.perQuestion,
    };
  }

  app.get(
    '/api/tests/:exam/attempts',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      if (!exam) {
        res.status(404).json({ error: 'unknown_exam' });
        return;
      }
      const user = currentUser(res);
      const { rows } = await db.query(
        `SELECT ${SUMMARY_COLS} FROM study.test_attempts
          WHERE user_id = $1 AND exam = $2 ORDER BY started_at DESC`,
        [user.userId, exam.id],
      );
      const history = rows.map(toSummary);
      const active = history.find((a) => a.submittedAt === null);
      res.json({ history, activeId: active?.attemptId ?? null });
    }),
  );

  app.post(
    '/api/tests/:exam/attempts',
    wrap(async (req, res) => {
      const exam = examById(param(req, 'exam'));
      if (!exam) {
        res.status(404).json({ error: 'unknown_exam' });
        return;
      }
      const body = parseBody(Start, req, res);
      if (!body) return;
      const user = currentUser(res);

      const { rows: active } = await db.query(
        'SELECT attempt_id FROM study.test_attempts WHERE user_id = $1 AND exam = $2 AND submitted_at IS NULL',
        [user.userId, exam.id],
      );
      if (active[0]) {
        res.status(409).json({ error: 'attempt_active', attemptId: String(active[0].attempt_id) });
        return;
      }

      // Exposure: practice ratings plus every question shown in a past attempt.
      const seen = new Map<string, number>();
      const { rows: reviewed } = await db.query(
        'SELECT question_id, right_count, wrong_count FROM study.review_state WHERE user_id = $1',
        [user.userId],
      );
      for (const r of reviewed) {
        seen.set(String(r.question_id), num(r.right_count) + num(r.wrong_count));
      }
      const { rows: past } = await db.query(
        'SELECT question_ids FROM study.test_attempts WHERE user_id = $1 AND exam = $2',
        [user.userId, exam.id],
      );
      for (const r of past) {
        for (const id of r.question_ids as string[]) seen.set(id, (seen.get(id) ?? 0) + 1);
      }

      let questionIds: string[];
      try {
        questionIds = sampleTest({ exam, bank: questions, seen });
      } catch (err) {
        if (err instanceof BankTooSmallError) {
          res.status(409).json({ error: 'bank_too_small', have: err.have, need: err.need });
          return;
        }
        throw err;
      }

      const limit = Math.min(body.timeLimitSecondsOverride ?? exam.minutes * 60, exam.minutes * 60);
      const { rows } = await db.query(
        `INSERT INTO study.test_attempts
           (user_id, exam, time_limit_seconds, deadline_at, question_ids, score_total, content_version)
         VALUES ($1, $2, $3, now() + make_interval(secs => $3), $4::jsonb, $5, $6)
         RETURNING attempt_id, started_at, deadline_at`,
        [user.userId, exam.id, limit, JSON.stringify(questionIds), questionIds.length, meta.content_version],
      );
      const row = rows[0];
      const body2: AttemptStart = {
        attemptId: String(row.attempt_id),
        questionIds,
        startedAt: iso(row.started_at) ?? '',
        deadlineAt: iso(row.deadline_at) ?? '',
        serverNow: new Date().toISOString(),
      };
      res.status(201).json(body2);
    }),
  );

  app.get(
    '/api/tests/attempts/:id',
    wrap(async (req, res) => {
      const user = currentUser(res);
      let row = await loadOwned(param(req, 'id'), user.userId);
      if (!row) {
        res.status(404).json({ error: 'unknown_attempt' });
        return;
      }
      const now = new Date();
      const deadline = new Date(String(iso(row.deadline_at)));
      if (!row.submitted_at && now.getTime() > deadline.getTime() + GRACE_MS) {
        // The tab was closed and the clock ran out: settle it as the timer would have.
        await submit(row, true);
        row = await loadOwned(param(req, 'id'), user.userId);
      }
      res.json(toAttempt(row, now));
    }),
  );

  app.put(
    '/api/tests/attempts/:id/answers',
    wrap(async (req, res) => {
      const body = parseBody(Answer, req, res);
      if (!body) return;
      const user = currentUser(res);
      const row = await loadOwned(param(req, 'id'), user.userId);
      if (!row) {
        res.status(404).json({ error: 'unknown_attempt' });
        return;
      }
      if (row.submitted_at) {
        res.status(409).json({ error: 'attempt_closed' });
        return;
      }
      const deadline = new Date(String(iso(row.deadline_at)));
      if (Date.now() > deadline.getTime() + GRACE_MS) {
        res.status(409).json({ error: 'attempt_expired' });
        return;
      }
      if (!(row.question_ids as string[]).includes(body.questionId)) {
        res.status(400).json({ error: 'question_not_in_attempt' });
        return;
      }
      await db.query(
        `UPDATE study.test_attempts
            SET answers = answers || jsonb_build_object($2::text, $3::text)
          WHERE attempt_id = $1`,
        [row.attempt_id, body.questionId, body.key],
      );
      res.status(204).end();
    }),
  );

  app.post(
    '/api/tests/attempts/:id/submit',
    wrap(async (req, res) => {
      const body = parseBody(Submit, req, res);
      if (!body) return;
      const user = currentUser(res);
      const row = await loadOwned(param(req, 'id'), user.userId);
      if (!row) {
        res.status(404).json({ error: 'unknown_attempt' });
        return;
      }
      if (row.submitted_at) {
        // Idempotent: return the recorded score.
        const questionIds = row.question_ids as string[];
        const answers = (row.answers as Partial<Record<string, OptionKey>>) ?? {};
        const result = grade(questionIds, answers, questionById);
        const out: ScoreResult = {
          attemptId: String(row.attempt_id),
          scoreCorrect: num(row.score_correct),
          scoreTotal: num(row.score_total),
          autoSubmitted: Boolean(row.auto_submitted),
          submittedAt: iso(row.submitted_at) ?? '',
          perQuestion: result.perQuestion,
        };
        res.json(out);
        return;
      }
      const deadline = new Date(String(iso(row.deadline_at)));
      const auto = Boolean(body.auto) || Date.now() > deadline.getTime();
      res.json(await submit(row, auto));
    }),
  );
}
