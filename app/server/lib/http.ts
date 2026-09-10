import type { NextFunction, Request, Response } from 'express';
import type { ZodType } from 'zod';

import type { Db } from './appkit';
import { identify, type Identity } from './user';

/**
 * Per-request identity, with the users row guaranteed to exist. The upsert
 * runs once per user per process; after that the FK constraints can rely on it.
 */
const ensured = new Set<string>();

export function userMiddleware(db: Db) {
  return async (req: Request, res: Response, next: NextFunction) => {
    const who = identify(req);
    if (!who) {
      res.status(401).json({ error: 'unauthenticated' });
      return;
    }
    try {
      if (!ensured.has(who.userId)) {
        await db.query(
          `INSERT INTO study.users (user_id, display_name)
             VALUES ($1, $2)
             ON CONFLICT (user_id) DO UPDATE
               SET display_name = COALESCE(EXCLUDED.display_name, study.users.display_name),
                   last_seen = now()`,
          [who.userId, who.displayName],
        );
        ensured.add(who.userId);
      }
      res.locals.user = who;
      next();
    } catch (err) {
      next(err);
    }
  };
}

export function currentUser(res: Response): Identity {
  const u = res.locals.user as Identity | undefined;
  if (!u) throw new Error('userMiddleware did not run');
  return u;
}

/** Parse a JSON body with a zod schema, answering 400 on failure. */
export function parseBody<T>(schema: ZodType<T>, req: Request, res: Response): T | null {
  const parsed = schema.safeParse(req.body ?? {});
  if (!parsed.success) {
    res.status(400).json({ error: 'invalid_body', issues: parsed.error.issues });
    return null;
  }
  return parsed.data;
}

type Handler = (req: Request, res: Response) => Promise<void> | void;

/** Route errors become a 500 with a log line instead of a hung request. */
export function wrap(handler: Handler) {
  return (req: Request, res: Response) => {
    Promise.resolve()
      .then(() => handler(req, res))
      .catch((err: unknown) => {
        console.error(`[api] ${req.method} ${req.path} failed:`, err);
        if (!res.headersSent) res.status(500).json({ error: 'internal' });
      });
  };
}

export function asDate(v: unknown): Date | null {
  if (v instanceof Date) return v;
  if (typeof v === 'string' || typeof v === 'number') return new Date(v);
  return null;
}

export function iso(v: unknown): string | null {
  const d = asDate(v);
  return d ? d.toISOString() : null;
}

export function num(v: unknown): number {
  return typeof v === 'number' ? v : Number(v);
}

/** Express 5 types a path param as string | string[]; routes here never repeat one. */
export function param(req: Request, name: string): string {
  const v = req.params[name];
  return Array.isArray(v) ? (v[0] ?? '') : (v ?? '');
}
