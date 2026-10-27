import { useCallback, useEffect, useState } from 'react';

import { isActive, label, type ResourceStatus, type UnitPresence, type UnitState } from '../../../shared/units';
import { CleanupConfirmError, useStore } from '../lib/store';

const POLL_MS = 4000;

type Confirm = { kind: 'setup'; others: UnitPresence[] } | { kind: 'cleanup' } | { kind: 'remove'; table: string };

/**
 * A unit's start page: every resource it uses, with a dot that is green only
 * when Unity Catalog has it right now, and the buttons that set it up and clean
 * it up. Setting a unit up first cleans any other unit still in the workspace
 * (after the learner confirms), so the shared schema holds one unit at a time.
 * The lessons and the assignment below stay greyed out until every set-up
 * resource exists: `onReady` says when.
 */
export function UnitResources({ unitId, onReady }: { unitId: string; onReady: (ready: boolean) => void }) {
  const store = useStore();
  const [state, setState] = useState<UnitState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<Confirm | null>(null);

  const load = useCallback(
    () =>
      store
        .unit(unitId)
        .then((s) => {
          setState(s);
          setError(null);
        })
        .catch((e: Error) => setError(e.message)),
    [store, unitId],
  );

  // SectionPage keys this by unit, so a new unit starts from a fresh state.
  useEffect(() => {
    void load();
  }, [load]);

  const running = isActive(state?.run ?? null) || isActive(state?.strayRun ?? null);
  useEffect(() => {
    if (!running) return;
    const t = window.setTimeout(() => void load(), POLL_MS);
    return () => window.clearTimeout(t);
  }, [running, state, load]);

  const settingUp = isActive(state?.run ?? null) && state?.run?.action === 'setup';
  useEffect(() => {
    onReady(!!state && state.ready && !settingUp);
  }, [state, settingUp, onReady]);

  const act = (fn: () => Promise<UnitState>) => {
    setBusy(true);
    setError(null);
    setConfirm(null);
    fn()
      .then(setState)
      .catch((e: Error) => {
        if (e instanceof CleanupConfirmError) setConfirm({ kind: 'setup', others: e.others });
        else setError(e.message);
      })
      .finally(() => setBusy(false));
  };

  if (!state) {
    return error ? <div className="error-banner">Could not read this unit&apos;s resources: {error}</div> : null;
  }

  const visible = (r: ResourceStatus) => !r.transient || r.exists === true;
  const setup = state.resources.filter((r) => r.group === 'setup' && visible(r));
  const work = state.resources.filter((r) => r.group !== 'setup' && visible(r));
  const setupDone = setup.filter((r) => r.exists === true).length;
  const run = state.run;
  const failed = run?.phase === 'failed' ? run : state.strayRun?.phase === 'failed' ? state.strayRun : null;

  const setupLabel =
    run?.phase === 'cleaning_others'
      ? `Removing ${run.targets.join(', ')}…`
      : run?.phase === 'setting_up'
        ? `Setting up… ${setupDone} of ${setup.length}`
        : state.ready && setup.length
          ? 'Set up again'
          : 'Set up unit resources';

  return (
    <div className="card unit-panel" aria-busy={running}>
      <div className="unit-head">
        <strong>{unitId} resources</strong>
        {state.quota ? <Quota {...state.quota} /> : null}
      </div>

      {!state.configured ? (
        <div className="notice">
          The app cannot see this workspace&apos;s Unity Catalog or its set-up and clean-up jobs from here, so nothing below
          is checked or locked. Set the unit up from a terminal with{' '}
          <code>databricks bundle run generate_datasets -t free --params section={unitId}</code>.
        </div>
      ) : null}

      <div className="unit-cols">
        <ResourceList title="Created by set-up" items={setup} />
        <ResourceList title="Created as you work" items={work} />
      </div>

      {state.others.length ? (
        <div className="unit-box">
          <div className="unit-box-title">Will be removed when you set this unit up</div>
          {state.others.map((o) => (
            <div key={o.unitId} className="unit-row">
              <Dot on /> {o.unitId} · {summary(o.resources)}
            </div>
          ))}
        </div>
      ) : null}

      {failed ? (
        <div className="error-banner unit-error">
          {failed.action === 'remove' ? 'Removing the table' : failed.action === 'cleanup' ? 'Clean-up' : 'Set-up'} failed: {failed.error}
        </div>
      ) : null}
      {error ? <div className="error-banner unit-error">{error}</div> : null}

      <div className="unit-actions">
        <button type="button" className="btn primary" disabled={busy || running || !state.configured} onClick={() => act(() => store.setupUnit(unitId))}>
          {running && run && isActive(run) && run.action === 'setup' ? <span className="spinner" aria-hidden="true" /> : null}
          {setupLabel}
        </button>
        <button type="button" className="btn ghost" disabled={busy || running || !state.configured} onClick={() => setConfirm({ kind: 'cleanup' })}>
          {run?.phase === 'cleaning' ? 'Cleaning up…' : 'Clean up resources'}
        </button>
        {state.setUpAt && !running ? <span className="muted unit-when">Set up {new Date(state.setUpAt).toLocaleString()}</span> : null}
      </div>
      <p className="unit-note">
        Clean-up removes only the resources listed here. Tables you create under other names you remove yourself.
      </p>

      {state.strays.length ? (
        <div className="unit-box">
          <div className="unit-box-title">Not managed by the app · {state.strays.length}</div>
          <p className="unit-note">
            No unit declares these, so clean-up won&apos;t remove them. They still count towards the schema&apos;s limit.
          </p>
          {state.strays.map((s) => (
            <div key={s.name} className="unit-row stray">
              <span>
                <code>{s.name}</code>
                {s.suggestion ? <span className="muted"> · did you mean {s.suggestion.split('.').pop()}?</span> : null}
              </span>
              <button
                type="button"
                className="btn ghost sm"
                disabled={busy || isActive(state.strayRun)}
                onClick={() => setConfirm({ kind: 'remove', table: s.name })}
              >
                {isActive(state.strayRun) && state.strayRun?.targets.includes(s.name) ? 'Removing…' : 'Remove'}
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {confirm ? (
        <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="unit-confirm-title">
          <div className="modal">
            {confirm.kind === 'setup' ? (
              <>
                <h2 id="unit-confirm-title">Remove other units&apos; resources first?</h2>
                <p>Setting up {unitId} removes these, so the shared schema holds one unit at a time:</p>
                {confirm.others.map((o) => (
                  <div key={o.unitId} className="unit-confirm-group">
                    <strong>{o.unitId}</strong>
                    <ul>
                      {o.resources.map((r) => (
                        <li key={`${r.kind}:${r.name}`}>
                          <code>{label(r)}</code>
                          {r.count ? ` (${r.count})` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <p>Your progress, grades and notebook outputs are kept.</p>
              </>
            ) : confirm.kind === 'cleanup' ? (
              <>
                <h2 id="unit-confirm-title">Clean up {unitId}?</h2>
                <p>
                  Every resource listed for this unit is removed: its data, the tables the lessons made, and the assignment&apos;s
                  outputs. Your progress, grades and notebook outputs are kept. Set the unit up again to continue.
                </p>
              </>
            ) : (
              <>
                <h2 id="unit-confirm-title">Remove this table?</h2>
                <p>
                  <code>{confirm.table}</code> is dropped. No unit declares it, so nothing in the app can bring it back.
                </p>
              </>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="btn primary"
                autoFocus
                onClick={() =>
                  act(() =>
                    confirm.kind === 'setup'
                      ? store.setupUnit(unitId, true)
                      : confirm.kind === 'cleanup'
                        ? store.cleanupUnit(unitId)
                        : store.removeStray(unitId, confirm.table),
                  )
                }
              >
                {confirm.kind === 'remove' ? 'Remove' : 'Confirm'}
              </button>
              <button type="button" className="btn ghost" onClick={() => setConfirm(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Dot({ on, unknown }: { on?: boolean; unknown?: boolean }) {
  return <span className={`dot${on ? ' on' : ''}${unknown ? ' unknown' : ''}`} aria-hidden="true" />;
}

function ResourceList({ title, items }: { title: string; items: ResourceStatus[] }) {
  return (
    <div>
      <div className="unit-group">{title}</div>
      {items.length ? (
        items.map((r) => (
          <div key={`${r.kind}:${r.name}`} className="unit-row" title={r.exists === null ? 'The app cannot check this kind of object' : r.name}>
            <Dot on={r.exists === true} unknown={r.exists === null} />
            <code>{label(r)}</code>
            {r.name.endsWith('*') ? <span className="muted"> ({r.count ?? 0})</span> : null}
            {r.optional ? <span className="nb-optional">Optional</span> : null}
            <span className="sr-only">{r.exists === true ? 'exists' : r.exists === false ? 'not created yet' : 'unknown'}</span>
          </div>
        ))
      ) : (
        <div className="unit-row muted">Nothing</div>
      )}
    </div>
  );
}

function Quota({ used, limit, schema }: { used: number; limit: number; schema: string }) {
  const pct = Math.min(100, Math.round((used / limit) * 100));
  return (
    <span className="unit-quota" title="Free Edition allows 100 tables (and views) per schema">
      {used} of {limit} tables in {schema.split('.').pop()}
      <span className="quota-bar">
        <span className={pct >= 80 ? 'bad' : pct >= 60 ? 'warn' : ''} style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}

function summary(rs: ResourceStatus[]): string {
  const counts = new Map<string, number>();
  for (const r of rs) {
    const k = r.kind === 'view' || r.kind === 'materialized_view' ? 'table' : r.kind;
    counts.set(k, (counts.get(k) ?? 0) + (r.count ?? 1));
  }
  return [...counts].map(([k, n]) => `${n} ${k}${n === 1 ? '' : 's'}`).join(', ');
}
