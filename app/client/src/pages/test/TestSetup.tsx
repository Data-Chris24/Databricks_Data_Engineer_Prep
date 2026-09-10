import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { familiesFor } from '../../../../shared/content';
import { Icon } from '../../components/Icon';
import { useExam } from '../../lib/exam';
import { AttemptActiveError, BankTooSmallError, useStore } from '../../lib/store';
import { formatDuration } from '../../lib/timer';

export function TestSetup() {
  const store = useStore();
  const navigate = useNavigate();
  const { examId, exam } = useExam();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [minutes, setMinutes] = useState(exam.minutes);
  const [minutesFor, setMinutesFor] = useState(examId);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const families = familiesFor(examId);
  const canTest = families >= exam.items;

  // Switching exam resets the timer field to that exam's official limit.
  if (minutesFor !== examId) {
    setMinutesFor(examId);
    setMinutes(exam.minutes);
  }

  useEffect(() => {
    store
      .attempts(examId)
      .then((a) => setActiveId(a.activeId))
      .catch(() => {});
  }, [store, examId]);

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const override = minutes < exam.minutes ? { timeLimitSecondsOverride: Math.max(60, Math.round(minutes * 60)) } : undefined;
      const a = await store.startAttempt(examId, override);
      void navigate(`/test/attempt/${a.attemptId}`, { replace: true });
    } catch (err) {
      if (err instanceof AttemptActiveError) {
        void navigate(`/test/attempt/${err.attemptId}`, { replace: true });
        return;
      }
      if (err instanceof BankTooSmallError) {
        setError(`This test needs ${err.need} questions and the bank has ${err.have}.`);
      } else {
        setError((err as Error).message);
      }
      setStarting(false);
    }
  };

  return (
    <div className="page page-narrow">
      <div className="kicker">Timed test · {exam.short}</div>
      <h1 className="display">Before you start</h1>
      <div className="card">
        <ul style={{ margin: '0 0 18px', paddingLeft: 20, lineHeight: 1.7 }}>
          <li>
            <b>{exam.items} questions</b>, sampled by the official section weightings.
          </li>
          <li>
            <b>{formatDuration(exam.minutes * 60)}</b>. The clock starts when you press Start and keeps running if you close the tab.
          </li>
          <li>No feedback until you submit. Move freely between questions; your answers save as you go.</li>
          <li>When time runs out the test submits itself. Unanswered questions count as wrong.</li>
          <li>Afterwards you get a score and can review every question, filtered to the ones you missed.</li>
        </ul>

        {!canTest ? (
          <div className="notice" style={{ marginBottom: 16 }}>
            {exam.short} test mode needs {exam.items} questions; the bank has {families}. Practice is available meanwhile.
          </div>
        ) : null}
        {error ? <div className="error-banner" style={{ marginBottom: 16 }}>{error}</div> : null}

        <details open={advanced} onToggle={(e) => setAdvanced((e.target as HTMLDetailsElement).open)} style={{ marginBottom: 18 }}>
          <summary className="muted" style={{ cursor: 'pointer' }}>
            Advanced: shorten the timer
          </summary>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10, fontSize: 14 }}>
            Time limit
            <input
              type="number"
              min={1}
              max={exam.minutes}
              value={minutes}
              onChange={(e) => setMinutes(Math.min(exam.minutes, Math.max(1, Number(e.target.value) || 1)))}
              style={{ width: 80, padding: '6px 8px', borderRadius: 6, border: '1px solid var(--line)', font: 'inherit', background: 'var(--surface)', color: 'inherit' }}
            />
            minutes (official: {exam.minutes}). A shorter time is recorded with the attempt.
          </label>
        </details>

        <div className="end-actions">
          {activeId ? (
            <Link to={`/test/attempt/${activeId}`} className="btn primary">
              Resume the test in progress <Icon name="arrow-right" size={16} stroke={2} />
            </Link>
          ) : (
            <button type="button" className="btn primary" disabled={!canTest || starting} onClick={() => void start()}>
              {starting ? 'Starting…' : 'Start the test'} <Icon name="timer" size={16} stroke={2} />
            </button>
          )}
          <Link to={`/test/${examId}`} className="btn ghost">
            Back
          </Link>
        </div>
      </div>
    </div>
  );
}
