import type { Application } from 'express';
import { z } from 'zod';

import { meta } from '../../shared/content';
import type { AppConfig, Me } from '../../shared/types';
import type { Db } from '../lib/appkit';
import { currentUser, parseBody, wrap } from '../lib/http';

/** Databricks Apps sets DATABRICKS_HOST; make sure it carries a scheme. */
export function workspaceHost(env: NodeJS.ProcessEnv = process.env): string | null {
  const raw = env.DATABRICKS_HOST?.trim();
  if (!raw) return null;
  const withScheme = /^https?:\/\//.test(raw) ? raw : `https://${raw}`;
  return withScheme.replace(/\/+$/, '');
}

const LastArea = z.object({ area: z.enum(['learn', 'test']) });

export function registerConfigRoutes(app: Application, db: Db) {
  app.get(
    '/api/config',
    wrap((_req, res) => {
      const body: AppConfig = {
        workspaceHost: workspaceHost(),
        filesRoot: process.env.DE_PREP_FILES_ROOT?.trim() || null,
        contentVersion: meta.content_version,
      };
      res.json(body);
    }),
  );

  app.get(
    '/api/me',
    wrap(async (_req, res) => {
      const user = currentUser(res);
      const { rows } = await db.query(
        'SELECT display_name, last_area FROM study.users WHERE user_id = $1',
        [user.userId],
      );
      const row = rows[0] ?? {};
      const body: Me = {
        userId: user.userId,
        displayName: (row.display_name as string | null) ?? user.displayName,
        lastArea: (row.last_area as Me['lastArea']) ?? null,
      };
      res.json(body);
    }),
  );

  app.put(
    '/api/me/last-area',
    wrap(async (req, res) => {
      const body = parseBody(LastArea, req, res);
      if (!body) return;
      const user = currentUser(res);
      await db.query('UPDATE study.users SET last_area = $2, last_seen = now() WHERE user_id = $1', [
        user.userId,
        body.area,
      ]);
      res.status(204).end();
    }),
  );
}
