import { createWorkspaceClient } from '@databricks/appkit';
import type { WorkspaceClient } from '@databricks/sdk-experimental';

import { LISTED_SCHEMAS, type UcSnapshot } from '../../shared/units';

/**
 * What exists in Unity Catalog and the raw volume, as the app's principal sees
 * it. Taken on every unit page load and every few seconds while a set-up or
 * clean-up runs: the registry in Lakebase records what the app did, but only
 * this decides whether a dot is green.
 *
 * Visibility is granted, not assumed: `account users` hold SELECT on the prep
 * schemas and READ VOLUME on `raw`, and the set-up job grants BROWSE on the
 * `workspace` catalog and on catalogs a unit creates, so `workspace.default`
 * and PRO-S8's catalogs can be listed too. Shares, recipients and connections
 * list only what the principal owns or administers; a list that fails or comes
 * back without the object leaves its dot unknown rather than wrong.
 */
export interface UcProbe {
  snapshot(paths: string[]): Promise<UcSnapshot>;
}

async function collect<T>(it: AsyncIterable<T>, limit = 2000): Promise<T[]> {
  const out: T[] = [];
  for await (const x of it) {
    out.push(x);
    if (out.length >= limit) break;
  }
  return out;
}

async function names<T>(fn: () => AsyncIterable<T>, pick: (x: T) => string | undefined): Promise<Set<string> | null> {
  try {
    return new Set((await collect(fn())).map(pick).filter((n): n is string => !!n).map((n) => n.toLowerCase()));
  } catch {
    return null;
  }
}

/** Existing paths among `paths`, by listing each distinct parent folder once. */
export async function existingPaths(
  paths: string[],
  list: (dir: string) => Promise<{ path: string; isDirectory: boolean }[] | null>,
): Promise<Set<string> | null> {
  const parents = new Map<string, string[]>();
  for (const p of paths) {
    const parent = p.slice(0, p.lastIndexOf('/'));
    parents.set(parent, [...(parents.get(parent) ?? []), p]);
  }
  const found = new Set<string>();
  let anyListed = false;
  for (const [parent, wanted] of parents) {
    const entries = await list(parent);
    if (!entries) continue;
    anyListed = true;
    const present = new Set(entries.map((e) => e.path.replace(/\/+$/, '')));
    for (const w of wanted) if (present.has(w)) found.add(w);
  }
  return anyListed || !paths.length ? found : null;
}

export function createUcProbe(client?: () => WorkspaceClient): UcProbe {
  let ws: WorkspaceClient | null = null;
  // AppKit's facade has no Unity Catalog services; the underlying SDK client does.
  const get = () => (ws ??= client ? client() : createWorkspaceClient().toLegacyWorkspaceClient());

  return {
    async snapshot(paths) {
      const w = get();
      const tables = new Set<string>();
      const tableSchemas = new Set<string>();
      for (const schema of LISTED_SCHEMAS) {
        const [catalog_name, schema_name] = schema.split('.');
        try {
          const list = await collect(w.tables.list({ catalog_name, schema_name, include_browse: true, omit_columns: true, omit_properties: true }));
          for (const t of list) if (t.full_name) tables.add(t.full_name.toLowerCase());
          tableSchemas.add(schema);
        } catch {
          // Not visible (no BROWSE on `default` yet): its tables stay unknown.
        }
      }
      if (!tableSchemas.size) throw new Error('no prep schema could be listed');
      const [functions, volumes, catalogs, shares, recipients, connections] = await Promise.all([
        names(() => w.functions.list({ catalog_name: 'workspace', schema_name: 'de_prep', include_browse: true }), (f) => f.full_name),
        names(() => w.volumes.list({ catalog_name: 'workspace', schema_name: 'de_prep', include_browse: true }), (v) => v.full_name),
        names(() => w.catalogs.list({ include_browse: true }), (c) => c.name),
        names(() => w.shares.listShares({}), (s) => s.name),
        names(() => w.recipients.list({}), (r) => r.name),
        names(() => w.connections.list({}), (c) => c.name),
      ]);
      const found = await existingPaths(paths, async (dir) => {
        try {
          const entries = await collect(w.files.listDirectoryContents({ directory_path: dir }));
          return entries.map((e) => ({ path: e.path ?? '', isDirectory: !!e.is_directory }));
        } catch {
          return null;
        }
      });
      return { tables, tableSchemas, functions, volumes, catalogs, shares, recipients, connections, paths: found };
    },
  };
}
