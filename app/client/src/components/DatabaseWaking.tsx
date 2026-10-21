import { useSyncExternalStore } from 'react';

import { databaseWaking } from '../lib/store';

/** Shown while a request waits for the database to come back (lib/store.ts). */
export function DatabaseWaking() {
  const waking = useSyncExternalStore(databaseWaking.subscribe, databaseWaking.get);
  if (!waking) return null;
  return (
    <div className="notice database-waking" role="status">
      <strong>Waking your study database…</strong> Databricks Free Edition switches it off after a few days unused. It
      is being turned back on, which takes a minute or two. Your progress is safe, and this page will load by itself.
    </div>
  );
}
