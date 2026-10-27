/**
 * A unit (an exam section) and the workspace resources it creates.
 *
 * Every section declares, in `grading/<SECTION>/resources.json`, the Unity
 * Catalog objects and raw-volume paths its set-up job, lessons and assignment
 * create (embedded in the content build as `notebooks[sid].resources`). The
 * unit's start page shows that list with a dot per resource, and the dot is
 * green only when the object really exists: the server takes a snapshot of
 * Unity Catalog on every page load (lesson set-up cells drop and recreate
 * tables, and learners drop their own), and this module judges the snapshot.
 *
 * One unit is set up at a time. Setting one up first cleans every other unit
 * that still has something in the workspace, so `workspace.de_prep` stays clear
 * of Free Edition's 100 tables per schema. Tables no unit declares are listed
 * as "not managed": clean-up never touches them, the learner may remove them.
 */

export type ResourceKind =
  | 'table'
  | 'view'
  | 'materialized_view'
  | 'function'
  | 'folder'
  | 'file'
  | 'volume'
  | 'catalog'
  | 'share'
  | 'recipient'
  | 'connection';

export type ResourceGroup = 'setup' | 'lesson' | 'assignment';

export interface DeclaredResource {
  kind: ResourceKind;
  /** Three-part for tables/views/functions/volumes (a table may end in `*`), a path for folders and files, a bare name otherwise. */
  name: string;
  /** Does not count towards the unit being worked through (an optional assignment's outputs). */
  optional?: boolean;
  /** The notebook removes it itself; shown only while it exists. */
  transient?: boolean;
}

export type UnitResources = Record<ResourceGroup, DeclaredResource[]>;

/** What the server could see. A null set means "could not be listed": its dots are unknown, not grey. */
export interface UcSnapshot {
  /** Lower-case full names of every table and view in the listed schemas. */
  tables: Set<string>;
  /** The schemas `tables` covers; a table elsewhere is unknown. */
  tableSchemas: Set<string>;
  functions: Set<string> | null;
  volumes: Set<string> | null;
  catalogs: Set<string> | null;
  shares: Set<string> | null;
  recipients: Set<string> | null;
  connections: Set<string> | null;
  /** Existing raw-volume paths among the ones asked about; null when the volume could not be listed. */
  paths: Set<string> | null;
}

export interface ResourceStatus extends DeclaredResource {
  group: ResourceGroup;
  /** true: exists. false: does not. null: the app cannot see this kind here. */
  exists: boolean | null;
  /** For a `*` table: how many tables match. */
  count?: number;
}

export interface UnitPresence {
  unitId: string;
  resources: ResourceStatus[];
}

export interface Stray {
  name: string;
  /** A declared name one or two edits away: a typo, most likely. */
  suggestion: string | null;
}

export type UnitAction = 'setup' | 'cleanup' | 'remove';
export type UnitPhase = 'cleaning_others' | 'setting_up' | 'cleaning' | 'removing' | 'done' | 'failed';

export interface UnitRun {
  action: UnitAction;
  phase: UnitPhase;
  runId: number | null;
  /** The units a set-up cleans first, or the tables a removal drops. */
  targets: string[];
  startedAt: string;
  finishedAt: string | null;
  error: string | null;
}

export interface UnitState {
  unitId: string;
  /** False when the jobs or Unity Catalog cannot be reached from here: nothing is gated then. */
  configured: boolean;
  resources: ResourceStatus[];
  /** Other units whose resources still exist: set-up removes them first. */
  others: UnitPresence[];
  strays: Stray[];
  quota: { used: number; limit: number; schema: string } | null;
  run: UnitRun | null;
  /** The last removal of a table no unit declares (run from any unit's page). */
  strayRun: UnitRun | null;
  setUpAt: string | null;
  /** Every set-up resource exists, so the lessons and the assignment can be opened. */
  ready: boolean;
}

export const RAW = '/Volumes/workspace/de_prep/raw';
export const QUOTA_SCHEMA = 'workspace.de_prep';
/** Free Edition's tables per schema (measured; the quota API returns nothing for a schema below it). */
export const TABLES_PER_SCHEMA = 100;
/** Where tables are looked for: the prep schemas, and `default`, where a missing `USE SCHEMA` lands. */
export const LISTED_SCHEMAS = ['workspace.de_prep', 'workspace.de_prep_staging', 'workspace.default'];
export const ACTIVE_PHASES: UnitPhase[] = ['cleaning_others', 'setting_up', 'cleaning', 'removing'];
const GROUPS: ResourceGroup[] = ['setup', 'lesson', 'assignment'];

export function isActive(run: UnitRun | null): boolean {
  return !!run && ACTIVE_PHASES.includes(run.phase);
}

export function flatten(res: UnitResources | undefined): (DeclaredResource & { group: ResourceGroup })[] {
  if (!res) return [];
  return GROUPS.flatMap((group) => (res[group] ?? []).map((r) => ({ ...r, group })));
}

function schemaOf(name: string): string {
  return name.toLowerCase().split('.').slice(0, 2).join('.');
}

/** `*` at the end of a declared table name matches any suffix. */
export function matches(pattern: string, name: string): boolean {
  const p = pattern.toLowerCase();
  const n = name.toLowerCase();
  return p.endsWith('*') ? n.startsWith(p.slice(0, -1)) : n === p;
}

function inSet(set: Set<string> | null, name: string): boolean | null {
  return set ? set.has(name.toLowerCase()) : null;
}

/** Every raw-volume path the snapshot must be asked about. */
export function pathsToProbe(all: Record<string, UnitResources>): string[] {
  const out = new Set<string>();
  for (const res of Object.values(all)) for (const r of flatten(res)) if (r.kind === 'folder' || r.kind === 'file') out.add(r.name);
  return [...out].sort();
}

export function statusOf(r: DeclaredResource & { group: ResourceGroup }, snap: UcSnapshot): ResourceStatus {
  switch (r.kind) {
    case 'table':
    case 'view':
    case 'materialized_view': {
      if (!snap.tableSchemas.has(schemaOf(r.name))) {
        // A table in a unit's own catalog (PRO-S8): known only through the catalog.
        // One in an unlisted `workspace` schema is simply unknown.
        const cat = r.name.split('.')[0].toLowerCase();
        return { ...r, exists: cat !== 'workspace' && snap.catalogs ? snap.catalogs.has(cat) : null };
      }
      if (r.name.endsWith('*')) {
        const count = [...snap.tables].filter((t) => matches(r.name, t)).length;
        return { ...r, exists: count > 0, count };
      }
      return { ...r, exists: snap.tables.has(r.name.toLowerCase()) };
    }
    case 'function':
      return { ...r, exists: inSet(snap.functions, r.name) };
    case 'volume':
      return { ...r, exists: inSet(snap.volumes, r.name) };
    case 'catalog':
      return { ...r, exists: inSet(snap.catalogs, r.name) };
    case 'share':
      return { ...r, exists: inSet(snap.shares, r.name) };
    case 'recipient':
      return { ...r, exists: inSet(snap.recipients, r.name) };
    case 'connection':
      return { ...r, exists: inSet(snap.connections, r.name) };
    case 'folder':
    case 'file':
      return { ...r, exists: snap.paths ? snap.paths.has(r.name) : null };
  }
}

/** Levenshtein distance, capped: anything over `max` returns max + 1. */
export function distance(a: string, b: string, max = 2): number {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      best = Math.min(best, cur[j]);
    }
    if (best > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

/** Tables in the listed schemas that no unit declares, each with its likeliest intended name. */
export function findStrays(all: Record<string, UnitResources>, snap: UcSnapshot): Stray[] {
  const declared = Object.values(all)
    .flatMap(flatten)
    .filter((r) => r.kind === 'table' || r.kind === 'view' || r.kind === 'materialized_view');
  const exact = declared.filter((r) => !r.name.endsWith('*')).map((r) => r.name.toLowerCase());
  const out: Stray[] = [];
  for (const t of [...snap.tables].sort()) {
    if (declared.some((r) => matches(r.name, t))) continue;
    const short = t.split('.').pop() ?? t;
    let suggestion: string | null = null;
    let best = 3;
    for (const d of exact) {
      const ds = d.split('.').pop() ?? d;
      const dist = distance(short, ds);
      if (dist < best) {
        best = dist;
        suggestion = d;
      }
    }
    out.push({ name: t, suggestion: best <= 2 && suggestion !== t ? suggestion : null });
  }
  return out;
}

/** Everything about one unit's page, from the declarations and a snapshot. */
export function unitView(
  unitId: string,
  all: Record<string, UnitResources>,
  snap: UcSnapshot | null,
): Pick<UnitState, 'resources' | 'others' | 'strays' | 'quota' | 'ready'> {
  if (!snap) {
    const resources = flatten(all[unitId]).map((r) => ({ ...r, exists: null }));
    return { resources, others: [], strays: [], quota: null, ready: true };
  }
  const resources = flatten(all[unitId]).map((r) => statusOf(r, snap));
  const others: UnitPresence[] = [];
  for (const [id, res] of Object.entries(all)) {
    if (id === unitId) continue;
    const present = flatten(res)
      .map((r) => statusOf(r, snap))
      .filter((r) => r.exists === true);
    if (present.length) others.push({ unitId: id, resources: present });
  }
  const used = [...snap.tables].filter((t) => schemaOf(t) === QUOTA_SCHEMA).length;
  const ready = resources.filter((r) => r.group === 'setup' && !r.transient).every((r) => r.exists !== false);
  return {
    resources,
    others,
    strays: findStrays(all, snap),
    quota: snap.tableSchemas.has(QUOTA_SCHEMA) ? { used, limit: TABLES_PER_SCHEMA, schema: QUOTA_SCHEMA } : null,
    ready,
  };
}

/** Short display name: `bronze_orders`, `raw/s2_teach/`, `catalog pro_s8_teach`. */
export function label(r: DeclaredResource): string {
  if (r.kind === 'folder') return `${r.name.replace(`${RAW}/`, 'raw/')}/`;
  if (r.kind === 'file') return r.name.replace(`${RAW}/`, 'raw/');
  if (r.kind === 'table' || r.kind === 'view' || r.kind === 'materialized_view' || r.kind === 'function' || r.kind === 'volume') {
    const [cat, sch, name] = r.name.split('.');
    const short = cat === 'workspace' && sch === 'de_prep' ? name : r.name;
    return r.kind === 'table' ? short : `${r.kind.replace('_', ' ')} ${short}`;
  }
  return `${r.kind} ${r.name}`;
}
