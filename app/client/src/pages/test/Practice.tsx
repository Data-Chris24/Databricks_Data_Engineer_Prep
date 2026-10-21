import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useSearchParams } from 'react-router';

import { questionsFor } from '../../../../shared/content';
import { keyForLabel, shuffledOrder } from '../../../../shared/optionOrder';
import { TEST_LEVELS, type OptionKey, type Quality, type Question, type ReviewRow, type TestLevel } from '../../../../shared/types';
import { LevelSwitch } from '../../components/LevelPicker';
import { Explanation, QuestionCard } from '../../components/QuestionCard';
import { ReadinessRail, type RailSection } from '../../components/ReadinessRail';
import { useExam } from '../../lib/exam';
import { useStore } from '../../lib/store';
import { PRACTICE_BATCH, PracticeBreak } from './PracticeBreak';

function due(row: ReviewRow | undefined, now: number): boolean {
  return !row || !row.dueAt || Date.parse(row.dueAt) <= now;
}

/** Prefer never-seen, then most-overdue; break ties randomly so order varies. */
export function pick(pool: Question[], reviews: Record<string, ReviewRow>, now = Date.now(), rng = Math.random): Question | null {
  if (!pool.length) return null;
  const ready = pool.filter((q) => due(reviews[q.id], now));
  const from = ready.length ? ready : pool;
  const unseen = from.filter((q) => !reviews[q.id]);
  // Shuffle first: the sort is stable, so without this every tie (all never-seen
  // questions, for a new learner) kept the bank's file order.
  const bucket = (unseen.length ? unseen : from).slice();
  for (let i = bucket.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [bucket[i], bucket[j]] = [bucket[j], bucket[i]];
  }
  bucket.sort((a, b) => (reviews[a.id]?.dueAt ? Date.parse(reviews[a.id].dueAt as string) : 0) - (reviews[b.id]?.dueAt ? Date.parse(reviews[b.id].dueAt as string) : 0));
  const head = bucket.slice(0, Math.max(1, Math.ceil(bucket.length * 0.35)));
  return head[Math.floor(rng() * head.length)];
}

export function Practice() {
  const store = useStore();
  const { examId, exam } = useExam();
  const [params, setParams] = useSearchParams();
  const sectionFilter = params.get('section');
  const levelParam = params.get('level') as TestLevel | null;
  const level: TestLevel = levelParam && TEST_LEVELS.includes(levelParam) ? levelParam : 'standard';
  /** Keep the other parameter when one changes. */
  const setParam = (key: 'section' | 'level', value: string | null) => {
    const next = new URLSearchParams(params);
    if (value && !(key === 'level' && value === 'standard')) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };
  const [reviews, setReviews] = useState<Record<string, ReviewRow>>({});
  const [loaded, setLoaded] = useState(false);
  const [current, setCurrent] = useState<Question | null>(null);
  /** A fresh option order every time a question is shown, so a position cannot be memorised. */
  const [seed, setSeed] = useState('');
  const order = useMemo(() => (current ? shuffledOrder(current, seed, level) : undefined), [current, seed, level]);
  const [chosen, setChosen] = useState<OptionKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** Questions rated since the last break; a break is offered every PRACTICE_BATCH. */
  const [answered, setAnswered] = useState(0);
  const [onBreak, setOnBreak] = useState(false);

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
      const q = pick(pool, rev);
      setCurrent(q);
      setSeed(String(Math.random()));
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
          setAnswered((n) => {
            const total = n + 1;
            if (total % PRACTICE_BATCH === 0) setOnBreak(true);
            return total;
          });
        })
        .catch((e: Error) => setError(e.message));
    },
    [current, next, store],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || !current || onBreak) return;
      const k = e.key.toUpperCase();
      if (chosen === null) {
        const key = order ? keyForLabel(order, k) : null;
        if (key) {
          e.preventDefault();
          setChosen(key);
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
  }, [current, chosen, rate, onBreak, order]);

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
        onSelect={(id) => setParam('section', id)}
      />
      <LevelSwitch exam={examId} section={sectionFilter} value={level} onChange={(l) => setParam('level', l)} />
      {error ? <div className="error-banner" style={{ marginBottom: 14 }}>{error}</div> : null}
      {onBreak ? <PracticeBreak sectionId={sectionFilter} answered={answered} onContinue={() => setOnBreak(false)} /> : null}
      {sectionFilter && current ? (
        <div className="row-between muted" style={{ marginBottom: 12, fontSize: 13.5 }}>
          <Link to={`/train/${examId}/${sectionFilter}`}>← Back to the lesson</Link>
          <span>A break is offered every {PRACTICE_BATCH} questions</span>
        </div>
      ) : null}

      {!current ? (
        <div className="card empty">
          <strong>No questions here yet</strong>
          The bank is still being written{sectionFilter ? ` for ${sectionFilter}` : ''}. Pick another section, or switch exam.
        </div>
      ) : (
        <QuestionCard question={current} mode="practice" order={order} chosen={chosen} revealed={chosen !== null} onChoose={(k) => chosen === null && setChosen(k)}>
          {chosen !== null ? (
            <>
              <Explanation question={current} chosen={chosen} order={order} />
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
