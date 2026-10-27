import type { Application } from 'express';

import { notebooks } from '../../shared/content';
import {
  isActive,
  pathsToProbe,
  type UcSnapshot,
  type UnitAction,
  type UnitPhase,
  type UnitResources,
  type UnitRun,
  type UnitState,
  flatten,
  statusOf,
  unitView,
} from '../../shared/units';
import type { AppKitLike, Db, JobHandle, JobRun } from '../lib/appkit';
import { isTerminal, taskRunId } from '../lib/grading';
import { currentUser, iso, param, wrap } from '../lib/http';
import type { UcProbe } from '../lib/uc';

/**
 * A unit's start page: what it uses, what other units still hold, what no unit
 * declares, and the set-up and clean-up that change it. See shared/units.ts.
 *
 * Two jobs do the work, both granted to the app rather than bound to it:
 * `generate_datasets` (set-up, parameter `section`) and `cleanup_unit`
 * (`sections`, `tables`). A set-up that must first clean other units runs the
 * clean-up, and when that succeeds the next page load starts the set-up: the
 * app moves its own run along as it polls, so no job writes to Lakebase.
 */
export const STRAYS = '_strays';

export interface Outcome {
  ok: boolean;
  error: string | null;
}

/** What a finished run means for the recorded one: the next phase, and whether to start the set-up. */
export function afterRun(run: Pick<UnitRun, 'action' | 'phase'>, outcome: Outcome): { phase: UnitPhase; startSetup: boolean } {
  if (!outcome.ok) return { phase: 'failed', startSetup: false };
  if (run.action === 'setup' && run.phase === 'cleaning_others') return { phase: 'setting_up', startSetup: true };
  return { phase: 'done', startSetup: false };
}

/** Whether a set-up may start now, and what it must clean first. */
export function planSetup(others: string[], confirm: boolean): { needsConfirm: boolean; clean: string[] } {
  if (others.length && !confirm) return { needsConfirm: true, clean: others };
  return { needsConfirm: false, clean: others };
}

/** A failed run's message: the notebook's own error when there is one. */
export function failureMessage(run: JobRun, outputError: string | null | undefined): string {
  const msg = outputError?.trim() || run.state?.state_message?.trim() || run.state?.result_state || 'the job failed';
  return msg.slice(0, 900);
}

const COLS = 'unit_id, action, phase, run_id, targets, started_at, finished_at, error, set_up_at, cleaned_at';

interface Row extends UnitRun {
  unitId: string;
  setUpAt: string | null;
  cleanedAt: string | null;
}

function toRow(r: Record<string, unknown>): Row {
  return {
    unitId: String(r.unit_id),
    action: String(r.action) as UnitAction,
    phase: String(r.phase) as UnitPhase,
    runId: r.run_id == null ? null : Number(r.run_id),
    targets: (typeof r.targets === 'string' ? r.targets : '').split(',').filter(Boolean),
    startedAt: iso(r.started_at) ?? new Date(0).toISOString(),
    finishedAt: iso(r.finished_at),
    error: (r.error as string | null) ?? null,
    setUpAt: iso(r.set_up_at),
    cleanedAt: iso(r.cleaned_at),
  };
}

function publicRun(row: Row | null): UnitRun | null {
  if (!row) return null;
  const { action, phase, runId, targets, startedAt, finishedAt, error } = row;
  return { action, phase, runId, targets, startedAt, finishedAt, error };
}

function allResources(): Record<string, UnitResources> {
  const out: Record<string, UnitResources> = {};
  for (const [id, nb] of Object.entries(notebooks)) if (nb.resources) out[id] = nb.resources;
  return out;
}

export function registerUnitRoutes(app: Application, db: Db, appkit: AppKitLike, probe: UcProbe) {
  const job = (key: string): JobHandle | null => {
    try {
      return appkit.jobs ? appkit.jobs(key) : null;
    } catch {
      return null;
    }
  };
  const setupJob = () => job('generate_datasets');
  const cleanupJob = () => job('cleanup_unit');
  const resources = allResources();
  const paths = pathsToProbe(resources);

  async function snapshot(): Promise<UcSnapshot | null> {
    try {
      return await probe.snapshot(paths);
    } catch (err) {
      console.error('[units] Unity Catalog snapshot failed:', (err as Error).message);
      return null;
    }
  }

  async function readRow(unitId: string): Promise<Row | null> {
    const { rows } = await db.query(`SELECT ${COLS} FROM study.unit_runs WHERE unit_id = $1`, [unitId]);
    return rows[0] ? toRow(rows[0]) : null;
  }

  async function start(handle: JobHandle | null, params: Record<string, string>): Promise<{ runId: number } | { error: string }> {
    if (!handle) return { error: 'the job is not deployed here' };
    const started = await handle.runNow({ job_parameters: params });
    if (!started.ok) {
      const e = started.error;
      return { error: (typeof e === 'string' ? e : (e as { message?: string }).message ?? 'could not start the job').slice(0, 500) };
    }
    return { runId: started.data.run_id };
  }

  async function record(unitId: string, action: UnitAction, phase: UnitPhase, runId: number | null, targets: string[], userId: string, error: string | null = null) {
    await db.query(
      `INSERT INTO study.unit_runs (unit_id, action, phase, run_id, targets, started_by, error, finished_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, CASE WHEN $3 IN ('done', 'failed') THEN now() END)
       ON CONFLICT (unit_id) DO UPDATE SET
         action = EXCLUDED.action, phase = EXCLUDED.phase, run_id = EXCLUDED.run_id, targets = EXCLUDED.targets,
         started_by = EXCLUDED.started_by, started_at = now(), finished_at = EXCLUDED.finished_at, error = EXCLUDED.error`,
      [unitId, action, phase, runId, targets.join(','), userId, error],
    );
  }

  /** Bring an active run up to date with its job, starting the set-up after a clean-up where due. */
  async function advance(row: Row): Promise<Row> {
    if (!isActive(row) || row.runId == null) return row;
    const handle = row.phase === 'setting_up' ? setupJob() : cleanupJob();
    if (!handle) return row;
    const got = await handle.getRun(row.runId);
    if (!got.ok || !isTerminal(got.data)) return row;
    const ok = got.data.state?.result_state === 'SUCCESS';
    let outputError: string | null = null;
    if (!ok) {
      const out = await handle.getRunOutput(taskRunId(got.data, row.runId));
      outputError = out.ok ? (out.data.error ?? null) : null;
    }
    const next = afterRun(row, { ok, error: ok ? null : failureMessage(got.data, outputError) });
    if (next.startSetup) {
      const started = await start(setupJob(), { section: row.unitId });
      if ('error' in started) {
        await db.query(`UPDATE study.unit_runs SET phase = 'failed', error = $2, finished_at = now() WHERE unit_id = $1`, [row.unitId, started.error]);
      } else {
        await db.query(`UPDATE study.unit_runs SET phase = 'setting_up', run_id = $2 WHERE unit_id = $1`, [row.unitId, started.runId]);
      }
      // The units it cleaned are no longer set up.
      await markCleaned(row.targets);
    } else if (next.phase === 'failed') {
      await db.query(`UPDATE study.unit_runs SET phase = 'failed', error = $2, finished_at = now() WHERE unit_id = $1`, [
        row.unitId,
        failureMessage(got.data, outputError),
      ]);
    } else {
      const stamp = row.action === 'setup' ? 'set_up_at = now(), cleaned_at = NULL' : row.action === 'cleanup' ? 'cleaned_at = now(), set_up_at = NULL' : 'error = NULL';
      await db.query(`UPDATE study.unit_runs SET phase = 'done', finished_at = now(), ${stamp} WHERE unit_id = $1`, [row.unitId]);
    }
    return (await readRow(row.unitId)) ?? row;
  }

  async function markCleaned(units: string[]) {
    if (!units.length) return;
    await db.query(
      `INSERT INTO study.unit_runs (unit_id, action, phase, cleaned_at, finished_at) SELECT u, 'cleanup', 'done', now(), now() FROM unnest($1::text[]) AS u
       ON CONFLICT (unit_id) DO UPDATE SET cleaned_at = now(), set_up_at = NULL
       WHERE study.unit_runs.phase NOT IN ('cleaning_others', 'setting_up', 'cleaning', 'removing')`,
      [units],
    );
  }

  /** Record when each declared resource appeared and disappeared, from what the snapshot saw. */
  async function remember(snap: UcSnapshot) {
    const seen: [string, string, string][] = [];
    const gone: [string, string, string][] = [];
    for (const [unitId, res] of Object.entries(resources)) {
      for (const r of flatten(res)) {
        const s = statusOf(r, snap);
        if (s.exists === true) seen.push([unitId, r.kind, r.name]);
        else if (s.exists === false) gone.push([unitId, r.kind, r.name]);
      }
    }
    const cols = (xs: [string, string, string][], i: number) => xs.map((x) => x[i]);
    if (seen.length) {
      await db.query(
        `INSERT INTO study.unit_resources (unit_id, kind, name)
         SELECT * FROM unnest($1::text[], $2::text[], $3::text[])
         ON CONFLICT (unit_id, kind, name) DO UPDATE SET
           created_at = CASE WHEN study.unit_resources.removed_at IS NULL THEN study.unit_resources.created_at ELSE now() END,
           removed_at = NULL`,
        [cols(seen, 0), cols(seen, 1), cols(seen, 2)],
      );
    }
    if (gone.length) {
      await db.query(
        `UPDATE study.unit_resources u SET removed_at = now()
         FROM unnest($1::text[], $2::text[], $3::text[]) AS g(unit_id, kind, name)
         WHERE u.unit_id = g.unit_id AND u.kind = g.kind AND u.name = g.name AND u.removed_at IS NULL`,
        [cols(gone, 0), cols(gone, 1), cols(gone, 2)],
      );
    }
  }

  async function state(unitId: string): Promise<UnitState> {
    let row = await readRow(unitId);
    if (row) row = await advance(row);
    let strayRow = await readRow(STRAYS);
    if (strayRow) strayRow = await advance(strayRow);
    const snap = await snapshot();
    if (snap) await remember(snap);
    const view = unitView(unitId, resources, snap);
    const configured = !!snap && !!setupJob() && !!cleanupJob();
    return {
      unitId,
      configured,
      ...view,
      ready: configured ? view.ready : true,
      run: publicRun(row),
      strayRun: publicRun(strayRow),
      setUpAt: row?.setUpAt ?? null,
    };
  }

  const known = (id: string) => !!resources[id];

  app.get(
    '/api/units/:unitId',
    wrap(async (req, res) => {
      const unitId = param(req, 'unitId');
      if (!known(unitId)) {
        res.status(404).json({ error: 'unknown_unit' });
        return;
      }
      res.json(await state(unitId));
    }),
  );

  /**
   * Set the unit up. When other units still hold resources, the first call
   * answers 409 with them (the page asks the learner), and `confirm: true`
   * cleans them before setting this one up.
   */
  app.post(
    '/api/units/:unitId/setup',
    wrap(async (req, res) => {
      const unitId = param(req, 'unitId');
      if (!known(unitId)) {
        res.status(404).json({ error: 'unknown_unit' });
        return;
      }
      const current = await state(unitId);
      if (isActive(current.run)) {
        res.json(current);
        return;
      }
      if (!current.configured) {
        res.status(503).json({ error: 'units_not_configured', state: current });
        return;
      }
      const confirm = (req.body as { confirm?: boolean } | undefined)?.confirm === true;
      const plan = planSetup(
        current.others.map((o) => o.unitId),
        confirm,
      );
      if (plan.needsConfirm) {
        res.status(409).json({ error: 'confirm_cleanup', others: current.others });
        return;
      }
      const user = currentUser(res).userId;
      const started = plan.clean.length
        ? await start(cleanupJob(), { sections: plan.clean.join(','), tables: '' })
        : await start(setupJob(), { section: unitId });
      if ('error' in started) {
        res.status(502).json({ error: 'unit_start_failed', message: started.error, state: current });
        return;
      }
      await record(unitId, 'setup', plan.clean.length ? 'cleaning_others' : 'setting_up', started.runId, plan.clean, user);
      res.json(await state(unitId));
    }),
  );

  app.post(
    '/api/units/:unitId/cleanup',
    wrap(async (req, res) => {
      const unitId = param(req, 'unitId');
      if (!known(unitId)) {
        res.status(404).json({ error: 'unknown_unit' });
        return;
      }
      const current = await state(unitId);
      if (isActive(current.run)) {
        res.json(current);
        return;
      }
      const started = await start(cleanupJob(), { sections: unitId, tables: '' });
      if ('error' in started) {
        res.status(502).json({ error: 'unit_start_failed', message: started.error, state: current });
        return;
      }
      await record(unitId, 'cleanup', 'cleaning', started.runId, [unitId], currentUser(res).userId);
      res.json(await state(unitId));
    }),
  );

  /** Remove one table no unit declares. Only a name the page currently lists as a stray is accepted. */
  app.post(
    '/api/units/:unitId/strays/remove',
    wrap(async (req, res) => {
      const unitId = param(req, 'unitId');
      const raw = (req.body as { table?: unknown } | undefined)?.table;
      const table = typeof raw === 'string' ? raw.toLowerCase() : '';
      if (!known(unitId)) {
        res.status(404).json({ error: 'unknown_unit' });
        return;
      }
      const current = await state(unitId);
      if (!current.strays.some((s) => s.name === table)) {
        res.status(400).json({ error: 'not_a_stray', state: current });
        return;
      }
      if (isActive(current.strayRun)) {
        res.status(409).json({ error: 'removal_running', state: current });
        return;
      }
      const started = await start(cleanupJob(), { sections: '', tables: table });
      if ('error' in started) {
        res.status(502).json({ error: 'unit_start_failed', message: started.error, state: current });
        return;
      }
      await record(STRAYS, 'remove', 'removing', started.runId, [table], currentUser(res).userId);
      res.json(await state(unitId));
    }),
  );
}
