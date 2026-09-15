import { createWorkspaceClient } from '@databricks/appkit';

/**
 * Fill in the environment the bundle would have passed when this deployment
 * did not come from the bundle.
 *
 * `bundle run study_app` sends the command and ~20 environment variables (the
 * Lakebase endpoint, one job id per grader, the files root) inside the
 * deployment request. Nothing lands in the source folder. So a deployment
 * started any other way - Start or Deploy in the Apps UI after the 24-hour
 * auto-stop, or `databricks apps deploy` - runs with app.yaml alone, which
 * can name the Lakebase resource but cannot know job ids. Without them the
 * jobs plugin refuses to start ("Missing required resources ... set
 * DATABRICKS_JOB_ID"), which is exactly what happened on 2026-09-14.
 *
 * The jobs carry stable names ("[DE prep] Grade ASSOC-S1", possibly behind a
 * development-mode prefix), and every grader's notebook lives under
 * `<files root>/grading/`, so both the job ids and the files root can be
 * recovered by listing the jobs the app's principal can see. Values already
 * in the environment always win; this only fills gaps.
 */

const MARKER = '[DE prep] ';

/** The env var the jobs plugin expects for a deployed job name, or null. */
export function jobEnvName(jobName: string): string | null {
  const i = jobName.indexOf(MARKER);
  if (i < 0) return null;
  const rest = jobName.slice(i + MARKER.length).trim();
  const grade = /^Grade ((?:ASSOC|PRO)-S\d+)$/i.exec(rest);
  if (grade) return `DATABRICKS_JOB_GRADE_${grade[1].toUpperCase().replace('-', '_')}`;
  if (/^Generate a section's datasets/i.test(rest)) return 'DATABRICKS_JOB_GENERATE_DATASETS';
  if (/^Reset an assignment/i.test(rest)) return 'DATABRICKS_JOB_RESET_ASSIGNMENT';
  return null;
}

/** The slice of a listed job this module reads. */
export interface DiscoveredJob {
  job_id?: number;
  settings?: {
    name?: string;
    tasks?: { notebook_task?: { notebook_path?: string } }[];
  };
}

type Env = Record<string, string | undefined>;

const REQUIRED = ['DATABRICKS_JOB_ID', 'DATABRICKS_JOB_RESET_ASSIGNMENT', 'DE_PREP_FILES_ROOT'] as const;

export function needsResolution(env: Env): boolean {
  return REQUIRED.some((k) => !env[k]?.trim());
}

/** Pure: the variables to add, given the current env and the visible jobs. */
export function resolveEnv(env: Env, jobs: DiscoveredJob[]): Record<string, string> {
  const out: Record<string, string> = {};
  let filesRoot: string | undefined;
  for (const job of jobs) {
    const name = job.settings?.name;
    if (!name || job.job_id == null) continue;
    const key = jobEnvName(name);
    if (!key) continue;
    if (!env[key]?.trim() && !out[key]) out[key] = String(job.job_id);
    const path = job.settings?.tasks?.[0]?.notebook_task?.notebook_path ?? '';
    const cut = path.indexOf('/grading/');
    if (cut > 0 && !filesRoot) filesRoot = path.slice(0, cut);
  }
  const anyJob = env.DATABRICKS_JOB_RESET_ASSIGNMENT ?? out.DATABRICKS_JOB_RESET_ASSIGNMENT ?? Object.values(out)[0];
  if (!env.DATABRICKS_JOB_ID?.trim() && anyJob) out.DATABRICKS_JOB_ID = anyJob;
  if (!env.DE_PREP_FILES_ROOT?.trim() && filesRoot) out.DE_PREP_FILES_ROOT = filesRoot;
  return out;
}

/** Resolve into `env` (process.env by default). Never throws: a failure here
 * leaves the app to start with whatever it has, and the log says why. */
export async function bootstrapEnv(env: Env = process.env, list?: () => Promise<DiscoveredJob[]>): Promise<Record<string, string>> {
  if (!needsResolution(env)) return {};
  console.log('[bootstrap] this deployment carried no bundle environment; resolving jobs by name');
  try {
    const jobs = await (list ?? listJobs)();
    const found = resolveEnv(env, jobs);
    for (const [k, v] of Object.entries(found)) env[k] = v;
    const keys = Object.keys(found);
    console.log(`[bootstrap] resolved ${keys.length} variable(s): ${keys.join(', ') || 'none'}`);
    if (needsResolution(env)) {
      console.error(`[bootstrap] still missing ${REQUIRED.filter((k) => !env[k]?.trim()).join(', ')}; is the bundle deployed, and can the app's principal see its jobs?`);
    }
    return found;
  } catch (err) {
    console.error('[bootstrap] could not list jobs:', err instanceof Error ? err.message : String(err));
    return {};
  }
}

async function listJobs(): Promise<DiscoveredJob[]> {
  // AppKit's facade has no Jobs listing; the underlying SDK client does.
  const ws = createWorkspaceClient().toLegacyWorkspaceClient();
  const jobs: DiscoveredJob[] = [];
  for await (const job of ws.jobs.list({ expand_tasks: true, limit: 100 })) jobs.push(job);
  return jobs;
}
