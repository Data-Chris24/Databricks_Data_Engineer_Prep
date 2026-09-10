import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { notebooks, notes } from '../../../../shared/content';
import type { GradingRun, TrainingState } from '../../../../shared/types';
import { Icon } from '../../components/Icon';
import { ProgressRing } from '../../components/ProgressRing';
import { useExam } from '../../lib/exam';
import { useStore } from '../../lib/store';
import { ResumeModal } from './ResumeModal';

const ASKED_KEY = (exam: string) => `de-prep.resume-asked.${exam}`;

export function TrainingHome() {
  const store = useStore();
  const navigate = useNavigate();
  const { examId, exam } = useExam();
  const [state, setState] = useState<TrainingState | null>(null);
  const [grades, setGrades] = useState<Record<string, GradingRun>>({});
  const [error, setError] = useState<string | null>(null);
  const [askResume, setAskResume] = useState(false);

  useEffect(() => {
    let alive = true;
    store
      .grading(examId)
      .then((g) => alive && setGrades(g))
      .catch(() => {});
    store
      .training(examId)
      .then((s) => {
        if (!alive) return;
        setState(s);
        let asked = false;
        try {
          asked = sessionStorage.getItem(ASKED_KEY(examId)) === '1';
        } catch {
          /* fine */
        }
        setAskResume(Boolean(s.resume) && !asked);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [store, examId]);

  const markAsked = () => {
    try {
      sessionStorage.setItem(ASKED_KEY(examId), '1');
    } catch {
      /* fine */
    }
    setAskResume(false);
  };

  const resumeSection = state?.resume ? exam.sections.find((s) => s.id === state.resume?.sectionId) : null;
  const completed = state ? Object.values(state.sections).filter((s) => s.completed).length : 0;
  const nextSection =
    exam.sections.find((s) => !state?.sections[s.id]?.completed && state?.sections[s.id]) ??
    exam.sections.find((s) => !state?.sections[s.id]?.completed) ??
    null;
  const heavy = [...exam.sections].sort((a, b) => b.weight - a.weight).slice(0, 2);

  return (
    <div className="page">
      {askResume && state?.resume && resumeSection ? (
        <ResumeModal
          sectionLabel={`S${resumeSection.number} · ${resumeSection.title}`}
          onContinue={() => {
            markAsked();
            const anchor = state.resume?.anchor ? `#${state.resume.anchor}` : '';
            void navigate(`/train/${examId}/${resumeSection.id}${anchor}`);
          }}
          onStartOver={async () => {
            await store.resetTraining(examId);
            markAsked();
            setState(await store.training(examId));
          }}
        />
      ) : null}

      <div className="learn-grid">
        <aside className="sticky">
          <div className="kicker">Learn · {exam.short}</div>
          <h1 className="display">Your progress</h1>
          <div className="card progress-card">
            <ProgressRing percent={state?.percentComplete ?? 0} />
            <div>
              <div style={{ fontFamily: 'var(--cond)', fontWeight: 600, fontSize: 20 }}>
                {completed} of {exam.sections.length} sections
              </div>
              <div className="section-sub" style={{ marginTop: 6 }}>
                Sections {heavy.map((s) => s.number).join(' and ')} are {heavy.reduce((n, s) => n + s.weight, 0)}% of
                the exam. Finish those first.
              </div>
            </div>
          </div>
          {nextSection ? (
            <Link to={`/train/${examId}/${nextSection.id}`} className="btn primary" style={{ marginTop: 18 }}>
              {state?.sections[nextSection.id] ? 'Continue' : 'Start'} · S{nextSection.number} {nextSection.title}
              <Icon name="arrow-right" size={18} stroke={2} />
            </Link>
          ) : state ? (
            <Link to={`/test/${examId}`} className="btn good" style={{ marginTop: 18 }}>
              <Icon name="check" size={16} stroke={2.5} /> All sections complete · go test yourself
            </Link>
          ) : null}
          {error ? (
            <div className="error-banner" style={{ marginTop: 16 }}>
              Progress could not be loaded: {error}
            </div>
          ) : null}
        </aside>

        <section>
          <div className="row-between" style={{ padding: '0 4px 10px' }}>
            <span className="rail-title">Sections in exam order</span>
            <span className="muted">Badge = share of the real exam</span>
          </div>
          <div className="section-list">
            {exam.sections.map((s) => {
              const p = state?.sections[s.id];
              const hasNotes = Boolean(notes[s.id]);
              const nbCount = notebooks[s.id]?.lessons.length ?? 0;
              const subCount = notes[s.id]?.subpages.length ?? 0;
              const current = nextSection?.id === s.id && p;
              const stateClass = p?.completed ? 'done' : p ? 'progress' : 'todo';
              return (
                <Link key={s.id} to={`/train/${examId}/${s.id}`} className={`section-row${current ? ' current' : ''}`}>
                  <span className="section-code">S{s.number}</span>
                  <span className="section-main">
                    <span className="section-title">{s.title}</span>
                    <span className="section-sub">
                      {s.objectives.length} objectives · {nbCount} notebook{nbCount === 1 ? '' : 's'}
                      {subCount ? ` · ${subCount} extra note` : ''}
                      {!hasNotes ? ' · notes coming soon' : ''}
                    </span>
                    {p && !p.completed && p.scrollPct ? (
                      <span className="mini-bar">
                        <div style={{ width: `${p.scrollPct}%` }} />
                      </span>
                    ) : null}
                  </span>
                  {grades[s.id]?.status === 'passed' ? (
                    <span className="state graded" title="Assignment passed">
                      <Icon name="check" size={14} stroke={2.5} /> Graded
                    </span>
                  ) : null}
                  <span className={`chip${s.weight >= 20 ? ' hot' : ''}`}>{s.weight}%</span>
                  <span className={`state ${stateClass}`}>
                    {p?.completed ? (
                      <>
                        <Icon name="check" size={14} stroke={2.5} /> Complete
                      </>
                    ) : p ? (
                      'In progress'
                    ) : (
                      'Not started'
                    )}
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
