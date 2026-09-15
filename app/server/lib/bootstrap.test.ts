import { describe, expect, it } from 'vitest';

import { bootstrapEnv, jobEnvName, needsResolution, resolveEnv } from './bootstrap';

const ROOT = '/Workspace/Users/sp/.bundle/databricks-de-prep/free/files';
const job = (id: number, name: string, path: string) => ({
  job_id: id,
  settings: { name, tasks: [{ notebook_task: { notebook_path: path } }] },
});
const deployed = [
  job(1, '[dev github_actions_ci] [DE prep] Grade ASSOC-S1', `${ROOT}/grading/ASSOC-S1/grade`),
  job(2, '[dev github_actions_ci] [DE prep] Grade PRO-S10', `${ROOT}/grading/PRO-S10/grade`),
  job(3, "[dev github_actions_ci] [DE prep] Reset an assignment's outputs", `${ROOT}/grading/reset_assignment`),
  job(4, '[dev github_actions_ci] [DE prep] Run ASSOC-S1 lessons', `${ROOT}/notebooks/lessons/associate/S1/01_x`),
  job(5, 'Somebody else’s job', '/Users/x/y'),
];

describe('jobEnvName', () => {
  it('maps graders and the reset job, through a development-mode prefix', () => {
    expect(jobEnvName('[DE prep] Grade ASSOC-S3')).toBe('DATABRICKS_JOB_GRADE_ASSOC_S3');
    expect(jobEnvName('[dev someone] [DE prep] Grade PRO-S10')).toBe('DATABRICKS_JOB_GRADE_PRO_S10');
    expect(jobEnvName("[DE prep] Reset an assignment's outputs")).toBe('DATABRICKS_JOB_RESET_ASSIGNMENT');
    expect(jobEnvName("[dev x] [DE prep] Generate a section's datasets")).toBe('DATABRICKS_JOB_GENERATE_DATASETS');
    // The per-section generate jobs exist for the terminal; the app binds only the dispatcher.
    expect(jobEnvName('[dev x] [DE prep] Generate ASSOC-S1 datasets')).toBeNull();
  });
  it('ignores lesson runners and unrelated jobs', () => {
    expect(jobEnvName('[DE prep] Run ASSOC-S1 lessons')).toBeNull();
    expect(jobEnvName('Grade ASSOC-S1')).toBeNull();
  });
});

describe('resolveEnv', () => {
  it('fills every gap from the visible jobs, including the files root', () => {
    const found = resolveEnv({}, deployed);
    expect(found).toEqual({
      DATABRICKS_JOB_GRADE_ASSOC_S1: '1',
      DATABRICKS_JOB_GRADE_PRO_S10: '2',
      DATABRICKS_JOB_RESET_ASSIGNMENT: '3',
      DATABRICKS_JOB_ID: '3',
      DE_PREP_FILES_ROOT: ROOT,
    });
  });
  it('never overrides what the bundle already set', () => {
    const env = { DATABRICKS_JOB_GRADE_ASSOC_S1: '99', DE_PREP_FILES_ROOT: '/elsewhere', DATABRICKS_JOB_ID: '7' };
    const found = resolveEnv(env, deployed);
    expect(found.DATABRICKS_JOB_GRADE_ASSOC_S1).toBeUndefined();
    expect(found.DE_PREP_FILES_ROOT).toBeUndefined();
    expect(found.DATABRICKS_JOB_ID).toBeUndefined();
    expect(found.DATABRICKS_JOB_GRADE_PRO_S10).toBe('2');
  });
  it('returns nothing when no prep jobs are visible', () => {
    expect(resolveEnv({}, [deployed[4]])).toEqual({});
  });
});

describe('bootstrapEnv', () => {
  it('is a no-op when the bundle supplied the environment', async () => {
    const env = { DATABRICKS_JOB_ID: '1', DATABRICKS_JOB_RESET_ASSIGNMENT: '3', DE_PREP_FILES_ROOT: ROOT };
    let listed = false;
    const found = await bootstrapEnv(env, () => { listed = true; return Promise.resolve(deployed); });
    expect(found).toEqual({});
    expect(listed).toBe(false);
  });
  it('writes the resolved values into the environment it was given', async () => {
    const env: Record<string, string | undefined> = {};
    await bootstrapEnv(env, () => Promise.resolve(deployed));
    expect(env.DATABRICKS_JOB_ID).toBe('3');
    expect(env.DE_PREP_FILES_ROOT).toBe(ROOT);
    expect(needsResolution(env)).toBe(false);
  });
  it('swallows a listing failure so the app still starts', async () => {
    const env: Record<string, string | undefined> = {};
    const found = await bootstrapEnv(env, () => Promise.reject(new Error('403')));
    expect(found).toEqual({});
  });
});
