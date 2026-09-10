import { useEffect, useState } from 'react';
import { Link } from 'react-router';

import { familiesFor, questionsFor } from '../../../../shared/content';
import { isDue } from '../../../../shared/sm2';
import type { AttemptSummary, ReviewRow } from '../../../../shared/types';
import { Icon } from '../../components/Icon';
import { useExam } from '../../lib/exam';
import { useStore } from '../../lib/store';
import { formatDuration } from '../../lib/timer';

function toState(r: ReviewRow) {
  return {
    n: r.n,
    ease: r.ease,
    dueAt: r.dueAt ? Date.parse(r.dueAt) : null,
    lastRatedAt: r.lastRatedAt ? Date.parse(r.lastRatedAt) : null,
    lastQuality: r.lastQuality as 0 | 1 | 2 | 3 | null,
    rightCount: r.rightCount,
    wrongCount: r.wrongCount,
  };
}

export function TestingHome() {
  const store = useStore();
  const { examId, exam } = useExam();
  const [reviews, setReviews] = useState<Record<string, ReviewRow> | null>(null);
  const [history, setHistory] = useState<AttemptSummary[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([store.practiceState(examId), store.attempts(examId)])
      .then(([r, a]) => {
        if (!alive) return;
        setReviews(r);
        setHistory(a.history);
        setActiveId(a.activeId);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [store, examId]);

  const pool = questionsFor(examId);
  const seen = pool.filter((q) => reviews?.[q.id]).length;
  const due = pool.filter((q) => isDue(reviews?.[q.id] ? toState(reviews[q.id]) : undefined)).length;
  const families = familiesFor(examId);
  const canTest = families >= exam.items;
  const best: number | null = history
    ? history.filter((h) => h.scoreCorrect !== null).reduce<number | null>((m, h) => Math.max(m ?? 0, h.scoreCorrect ?? 0), null)
    : null;

  return (
    <div className="page">
      <div className="kicker">Test · {exam.short}</div>
      <h1 className="display">How ready are you?</h1>
      <p className="lede">
        Practice gives feedback after every answer and schedules what you got wrong for a second look. Test mode sits you the
        real exam: {exam.items} questions, {formatDuration(exam.minutes * 60)}, nothing revealed until you submit.
      </p>
      {error ? <div className="error-banner">Could not load your history: {error}</div> : null}

      <div className="two-up">
        <div className="card">
          <h2>Practice</h2>
          <p>Answer, read why, rate your recall. Keys answer; 1–4 rate.</p>
          <div className="stat-row">
            <div className="stat">
              <b>{due}</b>
              <span>due now</span>
            </div>
            <div className="stat">
              <b>
                {seen}/{pool.length}
              </b>
              <span>seen</span>
            </div>
          </div>
          <Link to={`/test/${examId}/practice`} className="btn primary">
            Practice <Icon name="arrow-right" size={16} stroke={2} />
          </Link>
        </div>

        <div className="card">
          <h2>Timed test</h2>
          <p>
            {exam.items} questions in {formatDuration(exam.minutes * 60)}, drawn by section weighting. Unanswered questions count as wrong when time runs out.
          </p>
          {!canTest ? (
            <div className="notice" style={{ marginBottom: 14 }}>
              {exam.short} test mode needs {exam.items} questions; the bank has {families}. Practice mode is available while the bank grows.
            </div>
          ) : null}
          <div className="stat-row">
            <div className="stat">
              <b>{history?.length ?? 0}</b>
              <span>attempts</span>
            </div>
            <div className="stat">
              <b>{best === null ? '—' : `${Math.round((best / exam.items) * 100)}%`}</b>
              <span>best score</span>
            </div>
          </div>
          {activeId ? (
            <Link to={`/test/attempt/${activeId}`} className="btn primary">
              Resume test in progress <Icon name="arrow-right" size={16} stroke={2} />
            </Link>
          ) : (
            <Link to={`/test/${examId}/exam`} className={`btn primary${canTest ? '' : ' disabled'}`} aria-disabled={!canTest} onClick={(e) => !canTest && e.preventDefault()}>
              Start a test <Icon name="timer" size={16} stroke={2} />
            </Link>
          )}
        </div>
      </div>

      {history && history.length ? (
        <div className="card" style={{ marginTop: 18 }}>
          <h2>Past tests</h2>
          <table className="history">
            <thead>
              <tr>
                <th>Date</th>
                <th>Score</th>
                <th>Time used</th>
                <th>Ended</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {history.map((h) => {
                const used = h.submittedAt ? Math.round((Date.parse(h.submittedAt) - Date.parse(h.startedAt)) / 1000) : null;
                return (
                  <tr key={h.attemptId}>
                    <td>{new Date(h.startedAt).toLocaleString()}</td>
                    <td>
                      {h.scoreCorrect === null ? 'in progress' : `${h.scoreCorrect}/${h.scoreTotal} · ${Math.round((h.scoreCorrect / h.scoreTotal) * 100)}%`}
                    </td>
                    <td>{used === null ? '—' : formatDuration(used)}</td>
                    <td>{h.submittedAt ? (h.autoSubmitted ? 'time ran out' : 'submitted') : '—'}</td>
                    <td>
                      <Link to={h.submittedAt ? `/test/attempt/${h.attemptId}/review` : `/test/attempt/${h.attemptId}`}>
                        {h.submittedAt ? 'Review' : 'Resume'}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
