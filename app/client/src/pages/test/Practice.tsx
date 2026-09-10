import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { questionsFor } from '../../../../shared/content';
import type { OptionKey, Quality, Question, ReviewRow } from '../../../../shared/types';
import { Explanation, QuestionCard } from '../../components/QuestionCard';
import { ReadinessRail, type RailSection } from '../../components/ReadinessRail';
import { useExam } from '../../lib/exam';
import { useStore } from '../../lib/store';

function due(row: ReviewRow | undefined, now: number): boolean {
  return !row || !row.dueAt || Date.parse(row.dueAt) <= now;
}

/** Prefer never-seen, then most-overdue; break ties randomly so order varies. */
export function pick(pool: Question[], reviews: Record<string, ReviewRow>, now = Date.now(), rng = Math.random): Question | null {
  if (!pool.length) return null;
  const ready = pool.filter((q) => due(reviews[q.id], now));
  const from = ready.length ? ready : pool;
  const unseen = from.filter((q) => !reviews[q.id]);
  const bucket = (unseen.length ? unseen : from).slice();
  bucket.sort((a, b) => (reviews[a.id]?.dueAt ? Date.parse(reviews[a.id].dueAt as string) : 0) - (reviews[b.id]?.dueAt ? Date.parse(reviews[b.id].dueAt as string) : 0));
  const head = bucket.slice(0, Math.max(1, Math.ceil(bucket.length * 0.35)));
  return head[Math.floor(rng() * head.length)];
}

export function Practice() {
  const store = useStore();
  const { examId, exam } = useExam();
  const [params, setParams] = useSearchParams();
  const sectionFilter = params.get('section');
  const [reviews, setReviews] = useState<Record<string, ReviewRow>>({});
  const [loaded, setLoaded] = useState(false);
  const [current, setCurrent] = useState<Question | null>(null);
  const [chosen, setChosen] = useState<OptionKey | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pool = useMemo(() => questionsFor(examId, sectionFilter ?? undefined), [examId, sectionFilter]);

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    store
      .practiceState(examId)
      .then((r) => {
        if (!alive) return;
        setReviews(r);
        setLoaded(true);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [store, examId]);

  const next = useCallback(
    (rev: Record<string, ReviewRow>) => {
      setChosen(null);
      setCurrent(pick(pool, rev));
    },
    [pool],
  );

  useEffect(() => {
    if (loaded) next(reviews);
    // Only re-pick when the pool or load state changes, not on every rating.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, pool]);

  const rate = useCallback(
    (quality: Quality) => {
      if (!current) return;
      store
        .rate(current.id, quality)
        .then((row) => {
          setReviews((prev) => {
            const nextRev = { ...prev, [row.questionId]: row };
            next(nextRev);
            return nextRev;
          });
        })
        .catch((e: Error) => setError(e.message));
    },
    [current, next, store],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || !current) return;
      const k = e.key.toUpperCase();
      if (chosen === null) {
        if (k in current.options) {
          e.preventDefault();
          setChosen(k as OptionKey);
        }
        return;
      }
      const map: Record<string, Quality> = { '1': 0, '2': 1, '3': 2, '4': 3, ENTER: 2 };
      if (k in map) {
        e.preventDefault();
        rate(map[k]);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [current, chosen, rate]);

  const stats = useMemo(() => {
    const out: Record<string, RailSection> = {};
    for (const s of exam.sections) {
      const qs = questionsFor(examId, s.id);
      let right = 0;
      let total = 0;
      let seen = 0;
      for (const q of qs) {
        const r = reviews[q.id];
        if (!r) continue;
        seen += 1;
        right += r.rightCount;
        total += r.rightCount + r.wrongCount;
      }
      out[s.id] = { id: s.id, accuracy: total ? right / total : 0, seen, total: qs.length };
    }
    return out;
  }, [exam, examId, reviews]);

  const seenCount = pool.filter((q) => reviews[q.id]).length;
  const dueCount = pool.filter((q) => due(reviews[q.id], Date.now())).length;

  return (
    <div className="page page-narrow">
      <ReadinessRail
        exam={exam}
        stats={stats}
        selected={sectionFilter}
        onSelect={(id) => setParams(id ? { section: id } : {})}
      />
      {error ? <div className="error-banner" style={{ marginBottom: 14 }}>{error}</div> : null}

      {!current ? (
        <div className="card empty">
          <strong>No questions here yet</strong>
          The bank is still being written{sectionFilter ? ` for ${sectionFilter}` : ''}. Pick another section, or switch exam.
        </div>
      ) : (
        <QuestionCard question={current} mode="practice" chosen={chosen} revealed={chosen !== null} onChoose={(k) => chosen === null && setChosen(k)}>
          {chosen !== null ? (
            <>
              <Explanation question={current} chosen={chosen} />
              <div className="advance">
                <div className="advance-label">
                  Rate your recall to see the next question <span className="kbd">keys 1–4</span>
                </div>
                <div className="grade">
                  {(
                    [
                      ['again', 'Again', 0],
                      ['hard', 'Hard', 1],
                      ['good', 'Good', 2],
                      ['easy', 'Easy', 3],
                    ] as const
                  ).map(([cls, label, q]) => (
                    <button key={cls} type="button" className={`rate ${cls}`} onClick={() => rate(q)}>
                      <b>{label}</b>
                      <i>{q + 1}</i>
                    </button>
                  ))}
                </div>
                <button type="button" className="skip" onClick={() => next(reviews)}>
                  Skip without rating →
                </button>
              </div>
            </>
          ) : null}
        </QuestionCard>
      )}

      <div className="row-between muted" style={{ marginTop: 20 }}>
        <span>
          {sectionFilter ? `${sectionFilter} · ` : ''}
          {seenCount}/{pool.length} seen · {dueCount} due now
        </span>
        <span>Progress is saved to your account.</span>
      </div>
    </div>
  );
}
