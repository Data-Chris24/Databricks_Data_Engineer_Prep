import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';

import { examById, notes, questionById } from '../../../../shared/content';
import { suggestReview, type ReviewSuggestion } from '../../../../shared/reviewSuggestions';
import type { Attempt, ExamId, ScoreResult } from '../../../../shared/types';
import { Icon } from '../../components/Icon';
import { useStore } from '../../lib/store';
import { LEVEL_NAMES } from '../../lib/levels';
import { formatDuration } from '../../lib/timer';

export function useScored(id: string) {
  const store = useStore();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    store
      .attempt(id)
      .then(async (a) => {
        // submit() is idempotent on the server: for a finished attempt it just returns the record.
        const s = await store.submit(id, false);
        if (!alive) return;
        setAttempt(a);
        setScore(s);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [store, id]);
  return { attempt, score, error };
}

export function Score() {
  const { id = '' } = useParams();
  const { attempt, score, error } = useScored(id);

  const bySection = useMemo(() => {
    if (!score || !attempt) return [];
    const exam = examById(attempt.exam);
    if (!exam) return [];
    return exam.sections.map((s) => {
      const rows = score.perQuestion.filter((p) => questionById(p.id)?.section === s.id);
      return { id: s.id, number: s.number, title: s.title, correct: rows.filter((r) => r.isCorrect).length, total: rows.length };
    });
  }, [score, attempt]);

  if (error) return <div className="page page-narrow"><div className="error-banner">{error}</div></div>;
  if (!attempt || !score) return <div className="page page-narrow"><div className="card empty">Scoring…</div></div>;

  const pct = Math.round((score.scoreCorrect / score.scoreTotal) * 100);
  const used = Math.round((Date.parse(score.submittedAt) - Date.parse(attempt.startedAt)) / 1000);
  const unanswered = score.perQuestion.filter((p) => p.given === null).length;
  const exam = examById(attempt.exam);
  const suggestions = exam ? suggestReview(exam, score.perQuestion, questionById, notes) : [];

  return (
    <div className="page page-narrow">
      <div className="score-hero">
        <div className="kicker">
          Timed test · {exam?.short} · {LEVEL_NAMES[attempt.level]} · {new Date(attempt.startedAt).toLocaleString()}
        </div>
        <div className="score-big">
          {pct}
          <small>%</small>
        </div>
        <div style={{ fontFamily: 'var(--cond)', fontWeight: 600, fontSize: 22 }}>
          {score.scoreCorrect} of {score.scoreTotal} correct
        </div>
        <div className="muted" style={{ marginTop: 6 }}>
          {formatDuration(used)} of {formatDuration(attempt.timeLimitSeconds)} used
          {score.autoSubmitted ? ` · time ran out, ${unanswered} unanswered counted wrong` : unanswered ? ` · ${unanswered} left blank` : ''}
        </div>
      </div>

      <div className="breakdown">
        {bySection.map((s) => (
          <div key={s.id} className="cell">
            <b>
              {s.correct}/{s.total}
            </b>
            <span>
              S{s.number} · {s.title}
            </span>
          </div>
        ))}
      </div>

      {suggestions.length ? <WhatToReview exam={attempt.exam} suggestions={suggestions} /> : null}

      <div className="end-actions" style={{ justifyContent: 'center' }}>
        <Link to={`/test/attempt/${id}/review?filter=wrong`} className="btn primary">
          Review what you missed <Icon name="arrow-right" size={16} stroke={2} />
        </Link>
        <Link to={`/test/attempt/${id}/review`} className="btn ghost">
          Review all questions
        </Link>
        <Link to={`/test/${attempt.exam}`} className="btn ghost">
          Back to Test
        </Link>
      </div>
    </div>
  );
}

/** Most-missed first; the rest are one click away in the section itself. */
const OBJECTIVES_SHOWN = 3;

/** Where the misses cost the most on the real exam, with a way into each (shared/reviewSuggestions.ts). */
function WhatToReview({ exam, suggestions }: { exam: ExamId; suggestions: ReviewSuggestion[] }) {
  return (
    <section className="card review-next">
      <h2>What to review next</h2>
      <p className="muted">
        Ranked by how much of the real exam each section&rsquo;s misses stand for. One test gives a section only a few
        questions, so read a single miss as a hint, not a verdict.
      </p>
      {suggestions.map((s) => (
        <div key={s.sectionId} className="review-next-item">
          <div className="row-between">
            <strong>
              S{s.number} · {s.title}
            </strong>
            <span className="muted">
              {s.correct}/{s.total} right · {s.weight}% of the exam · costs about {s.pointsLost.toFixed(1)}%
            </span>
          </div>
          {s.total <= 3 ? (
            <div className="muted small">
              Only {s.total} question{s.total === 1 ? '' : 's'} from this section in the test.
            </div>
          ) : null}
          {s.objectives.length ? (
            <ul>
              {s.objectives.slice(0, OBJECTIVES_SHOWN).map((o) => (
                <li key={o.id}>
                  {o.anchor ? <Link to={`/train/${exam}/${s.sectionId}#${o.anchor}`}>{o.text}</Link> : o.text}{' '}
                  <span className="chip obj">{o.id}</span>
                  {o.missed > 1 ? <span className="muted"> · missed {o.missed}</span> : null}
                </li>
              ))}
              {s.objectives.length > OBJECTIVES_SHOWN ? (
                <li className="muted">
                  and {s.objectives.length - OBJECTIVES_SHOWN} more objective
                  {s.objectives.length - OBJECTIVES_SHOWN === 1 ? '' : 's'} in this section
                </li>
              ) : null}
            </ul>
          ) : null}
          <div className="end-actions">
            <Link to={`/train/${exam}/${s.sectionId}`} className="btn ghost sm">
              Open the section
            </Link>
            <Link to={`/test/${exam}/practice?section=${s.sectionId}`} className="btn ghost sm">
              Practice this section <Icon name="arrow-right" size={14} stroke={2} />
            </Link>
          </div>
        </div>
      ))}
    </section>
  );
}
