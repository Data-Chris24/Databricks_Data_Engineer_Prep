import type { Request } from 'express';

/**
 * Who is calling. Databricks Apps forwards the signed-in user's identity as
 * headers on every request; locally there is no proxy, so DEV_USER_EMAIL in
 * server/.env stands in. Anything else is unauthenticated.
 */
export interface Identity {
  userId: string;
  displayName: string | null;
}

function header(req: Request, name: string): string | null {
  const v = req.headers[name];
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}

export function identify(req: Request): Identity | null {
  const email = header(req, 'x-forwarded-email') ?? process.env.DEV_USER_EMAIL ?? null;
  if (!email) return null;
  const preferred = header(req, 'x-forwarded-preferred-username');
  return { userId: email.trim().toLowerCase(), displayName: preferred ?? null };
}
