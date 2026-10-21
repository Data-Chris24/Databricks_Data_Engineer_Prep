import type { Db } from '../lib/appkit';
import { migrations } from './migrations';

/**
 * Apply every migration whose version is not yet recorded. The first migration
 * creates the migrations table itself, so the "applied" lookup tolerates its
 * absence.
 */
export async function migrate(db: Db, log: (msg: string) => void = console.log): Promise<number> {
  let applied = new Set<number>();
  try {
    const { rows } = await db.query('SELECT version FROM study.schema_migrations');
    applied = new Set(rows.map((r) => Number(r.version)));
  } catch {
    // Schema does not exist yet - the first migration will create it.
  }

  let count = 0;
  for (const m of migrations) {
    if (applied.has(m.version)) continue;
    await db.query('BEGIN');
    try {
      await db.query(m.sql);
      await db.query(
        'INSERT INTO study.schema_migrations (version, name) VALUES ($1, $2) ON CONFLICT DO NOTHING',
        [m.version, m.name],
      );
      await db.query('COMMIT');
    } catch (err) {
      await db.query('ROLLBACK');
      throw err;
    }
    count += 1;
    log(`[db] applied migration ${m.version} (${m.name})`);
  }
  log(`[db] migrations applied: ${count}, current version ${migrations.at(-1)?.version ?? 0}`);
  return count;
}
