import { useCallback, useEffect, useRef, useState } from 'react';

import type { GradingRun } from '../../../shared/types';
import { ApiError, GradingInProgressError, useStore } from '../lib/store';
import { Icon } from './Icon';

const POLL_MS = 8000;

/**
 * "Grade my assignment": triggers the section's grading job on the learner's
 * behalf and shows the result inline. The learner never opens the job.
 */
export function GradingPanel({ sectionId, gradeJob, onResult }: { sectionId: string; gradeJob: string | null; onResult?: (run: GradingRun) => void }) {
  const store = useStore();
  const [run, setRun] = useState<GradingRun | null>(null);
  const [configured, setConfigured] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const load = useCallback(() => {
    store
      .gradingRun(sectionId)
      .then((r) => {
        setRun(r.run);
        setConfigured(r.configured);
        if (r.run && (r.run.status === 'passed' || r.run.status === 'failed')) onResult?.(r.run);
      })
      .catch((e: Error) => setError(e.message));
  }, [store, sectionId, onResult]);

  useEffect(() => {
    load();
  }, [load]);

  const inFlight = run?.status === 'queued' || run?.status === 'running';
  useEffect(() => {
    if (!inFlight) return;
    timer.current = window.setInterval(load, POLL_MS);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [inFlight, load]);

  const start = () => {
    setBusy(true);
    setError(null);
    store
      .grade(sectionId)
      .then(setRun)
      .catch((e: unknown) => {
        if (e instanceof GradingInProgressError) setRun(e.run);
        else if (e instanceof ApiError && e.message === 'grading_not_configured') setConfigured(false);
        else setError((e as Error).message);
      })
      .finally(() => setBusy(false));
  };

  const cli = gradeJob ? `databricks bundle run ${gradeJob} -t free --profile FREE` : null;

  return (
    <div className="grading">
      <div className="row-between">
        <div>
          <div className="rail-title">Grade my assignment</div>
          <div className="muted">Runs the checks for this section against the tables you produced. Takes a few minutes on serverless.</div>
        </div>
        <button type="button" className="btn primary" onClick={start} disabled={busy || inFlight || !configured}>
          {inFlight ? 'Grading…' : run ? 'Grade again' : 'Grade my assignment'} <Icon name="flag" size={16} stroke={2} />
        </button>
      </div>

      {!configured ? (
        <div className="notice" style={{ marginTop: 12 }}>
          Grading from the app is not set up in this environment.{cli ? <> Run it from a terminal instead: <code>{cli}</code></> : null}
        </div>
      ) : null}
      {error ? <div className="error-banner" style={{ marginTop: 12 }}>{error}</div> : null}

      {run ? (
        <div className={`grade-result ${run.status}`} style={{ marginTop: 14 }}>
          {inFlight ? (
            <div className="grade-line">
              <span className="spinner" aria-hidden="true" /> {run.status === 'queued' ? 'Queued' : 'Running the checks'}… started {new Date(run.startedAt).toLocaleTimeString()}
            </div>
          ) : run.status === 'passed' ? (
            <div className="grade-line">
              <Icon name="check" size={18} stroke={2.5} /> <b>Passed</b> · all {run.result?.total ?? ''} checks satisfied · {run.finishedAt ? new Date(run.finishedAt).toLocaleString() : ''}
            </div>
          ) : run.status === 'failed' ? (
            <>
              <div className="grade-line">
                <b>Not yet</b> · {run.result?.failed.length ?? 0} of {run.result?.total ?? 0} checks failed · {run.finishedAt ? new Date(run.finishedAt).toLocaleString() : ''}
              </div>
              <ul className="grade-fails">
                {run.result?.failed.map((f) => (
                  <li key={f.test}>
                    <code>{f.test}</code>
                    {f.message ? <pre>{f.message}</pre> : null}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="grade-line">
              <b>The grader could not run</b> · {run.error ?? 'unknown error'}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
