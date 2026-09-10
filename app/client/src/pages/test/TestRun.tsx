import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router';

import { questionById } from '../../../../shared/content';
import type { Attempt, OptionKey } from '../../../../shared/types';
import { Countdown } from '../../components/Countdown';
import { Icon } from '../../components/Icon';
import { QuestionCard } from '../../components/QuestionCard';
import { ApiError, useStore } from '../../lib/store';
import { createClock, type Clock } from '../../lib/timer';

export function TestRun() {
  const store = useStore();
  const navigate = useNavigate();
  const { id = '' } = useParams();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [clock, setClock] = useState<Clock | null>(null);
  const [answers, setAnswers] = useState<Partial<Record<string, OptionKey>>>({});
  const [index, setIndex] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);

  useEffect(() => {
    let alive = true;
    store
      .attempt(id)
      .then((a) => {
        if (!alive) return;
        if (a.submittedAt) {
          void navigate(`/test/attempt/${id}/score`, { replace: true });
          return;
        }
        setAttempt(a);
        setAnswers(a.answers);
        setClock(createClock(a.serverNow));
        const firstBlank = a.questionIds.findIndex((q) => !a.answers[q]);
        setIndex(firstBlank >= 0 ? firstBlank : 0);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [store, id, navigate]);

  const submit = useCallback(
    (auto: boolean) => {
      if (submitting.current) return;
      submitting.current = true;
      store
        .submit(id, auto)
        .then(() => navigate(`/test/attempt/${id}/score`, { replace: true }))
        .catch((e: Error) => {
          submitting.current = false;
          setError(e.message);
        });
    },
    [store, id, navigate],
  );

  const onExpire = useCallback(() => submit(true), [submit]);

  const choose = (questionId: string, key: OptionKey) => {
    setAnswers((prev) => ({ ...prev, [questionId]: key }));
    store.answer(id, questionId, key).catch((e: unknown) => {
      if (e instanceof ApiError && (e.message === 'attempt_expired' || e.message === 'attempt_closed')) submit(true);
      else setError((e as Error).message);
    });
  };

  const questionId = attempt?.questionIds[index];
  const question = questionId ? questionById(questionId) : undefined;
  const answered = useMemo(() => (attempt ? attempt.questionIds.filter((q) => answers[q]).length : 0), [attempt, answers]);

  useEffect(() => {
    if (!attempt) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toUpperCase();
      if (question && k in question.options) {
        e.preventDefault();
        choose(question.id, k as OptionKey);
      } else if (e.key === 'ArrowRight' || e.key === 'n') setIndex((i) => Math.min(attempt.questionIds.length - 1, i + 1));
      else if (e.key === 'ArrowLeft' || e.key === 'p') setIndex((i) => Math.max(0, i - 1));
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, question]);

  if (error) {
    return (
      <div className="page page-narrow">
        <div className="error-banner">{error}</div>
      </div>
    );
  }
  if (!attempt || !clock || !question) {
    return (
      <div className="page page-narrow">
        <div className="card empty">Loading your test…</div>
      </div>
    );
  }

  const total = attempt.questionIds.length;
  const unanswered = total - answered;

  return (
    <div className="page page-narrow">
      <div className="test-bar">
        <div>
          <div className="kicker">Timed test · {attempt.exam}</div>
          <div style={{ fontFamily: 'var(--cond)', fontWeight: 600, fontSize: 20 }}>
            Question {index + 1} of {total}
          </div>
        </div>
        <Countdown deadlineAt={attempt.deadlineAt} clock={clock} onExpire={onExpire} />
      </div>

      <QuestionCard question={question} mode="test" chosen={answers[question.id] ?? null} onChoose={(k) => choose(question.id, k)} />

      <div className="nav-row">
        <button type="button" className="btn ghost" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          <Icon name="arrow-left" size={16} stroke={2} /> Previous
        </button>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {index < total - 1 ? (
            <button type="button" className="btn primary" onClick={() => setIndex(index + 1)}>
              Next <Icon name="arrow-right" size={16} stroke={2} />
            </button>
          ) : null}
          <button type="button" className={`btn ${index < total - 1 ? 'ghost' : 'primary'}`} onClick={() => setConfirming(true)}>
            Submit test <Icon name="flag" size={16} stroke={2} />
          </button>
        </div>
      </div>

      {confirming ? (
        <div className="card" style={{ marginTop: 18, borderColor: 'var(--accent)' }}>
          <h2>Submit now?</h2>
          <p>
            {unanswered === 0 ? 'Every question has an answer.' : `${unanswered} question${unanswered === 1 ? ' is' : 's are'} unanswered and will count as wrong.`}{' '}
            You cannot change answers after submitting.
          </p>
          <div className="end-actions">
            <button type="button" className="btn primary" onClick={() => submit(false)}>
              Submit and see my score
            </button>
            <button type="button" className="btn ghost" onClick={() => setConfirming(false)}>
              Keep going
            </button>
          </div>
        </div>
      ) : null}

      <div className="palette" aria-label="Question palette">
        {attempt.questionIds.map((q, i) => (
          <button
            key={q}
            type="button"
            className={[answers[q] ? 'answered' : '', i === index ? 'current' : ''].join(' ')}
            onClick={() => setIndex(i)}
            aria-label={`Question ${i + 1}${answers[q] ? ', answered' : ''}`}
          >
            {i + 1}
          </button>
        ))}
      </div>
      <div className="muted" style={{ marginTop: 10 }}>
        {answered}/{total} answered · letters answer, <span className="kbd">←</span> <span className="kbd">→</span> move
      </div>
    </div>
  );
}
