import { useCallback, useEffect, useRef, useState } from 'react';

import type { DatasetState } from '../../../shared/types';
import { useStore } from '../lib/store';
import { Icon } from './Icon';

const POLL_MS = 8000;

/**
 * The section's data, prepared from inside the app. On first open of a section
 * whose generate job has never run, this starts it and shows progress; the
 * lesson notebooks and the assignment read the tables it creates, so the
 * learner never has to run a bundle command from a terminal.
 */
export function DatasetBand({ sectionId }: { sectionId: string }) {
  const store = useStore();
  const [state, setState] = useState<DatasetState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);
  const autoStarted = useRef(false);

  const prepare = useCallback(
    (force: boolean) => {
      setBusy(true);
      setError(null);
      store
        .prepareDatasets(sectionId, force)
        .then(setState)
        .catch((e: Error) => setError(e.message))
        .finally(() => setBusy(false));
    },
    [store, sectionId],
  );

  useEffect(() => {
    let alive = true;
    const load = () => {
      store
        .datasets(sectionId)
        .then((s) => {
          if (!alive) return;
          setState(s);
          // Never generated here: start it now, once, without asking. That is the
          // whole point of the band.
          if (s.status === 'missing' && !autoStarted.current) {
            autoStarted.current = true;
            prepare(false);
          }
          if (s.status === 'preparing') timer.current = window.setTimeout(load, POLL_MS);
        })
        .catch((e: Error) => alive && setError(e.message));
    };
    load();
    return () => {
      alive = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [store, sectionId, prepare]);

  // Keep polling after a prepare() flipped the state to preparing.
  useEffect(() => {
    if (state?.status !== 'preparing') return;
    const t = window.setTimeout(() => {
      store
        .datasets(sectionId)
        .then(setState)
        .catch(() => {});
    }, POLL_MS);
    return () => window.clearTimeout(t);
  }, [state, store, sectionId]);

  if (!state && !error) return null;
  const status = state?.status ?? 'failed';
  const cls = status === 'ready' ? 'good' : status === 'preparing' ? 'progress' : 'warn';

  return (
    <div className={`card data-band ${cls}`} role="status">
      {status === 'preparing' ? (
        <>
          <span className="spinner" aria-hidden="true" />
          <span>
            <strong>Preparing this section&apos;s data</strong> in your workspace (about a minute). The notebooks below work once it is done.
          </span>
        </>
      ) : status === 'ready' ? (
        <>
          <Icon name="check" size={16} stroke={2.5} />
          <span>
            <strong>Section data is ready</strong>
            {state?.finishedAt ? <span className="muted"> · generated {new Date(state.finishedAt).toLocaleString()}</span> : null}
          </span>
          <button type="button" className="skip" onClick={() => prepare(true)} disabled={busy} title="Runs the generate job again; the teach and assess tables are rebuilt from scratch">
            Regenerate
          </button>
        </>
      ) : status === 'unconfigured' ? (
        <span>
          <strong>The app cannot prepare this section&apos;s data here.</strong> Run{' '}
          <code>databricks bundle run generate_datasets_{sectionId.toLowerCase().replace('-', '_')} -t free</code> from a terminal.
        </span>
      ) : (
        <>
          <Icon name="flag" size={16} stroke={2} />
          <span>
            <strong>Preparing the data failed.</strong> {error ?? state?.error ?? ''}
          </span>
          <button type="button" className="btn ghost" onClick={() => prepare(true)} disabled={busy}>
            Try again
          </button>
        </>
      )}
    </div>
  );
}
