import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';

import { exams, familiesFor, notes, notebooks } from '../../../shared/content';
import type { Area } from '../../../shared/types';
import { ExamSwitch } from '../components/ExamSwitch';
import { Icon } from '../components/Icon';
import { useExam } from '../lib/exam';
import { useStore } from '../lib/store';

const AREA_WORD: Record<Area, string> = { learn: 'learning', test: 'testing' };

export function headline(side: Area | null, lastArea: Area | null): string {
  if (side) return `Let's get started ${AREA_WORD[side]} Databricks Data Engineering!`;
  if (lastArea) return `Continue ${AREA_WORD[lastArea]} Databricks Data Engineering skills?`;
  return 'How would you like to begin?';
}

export function Home() {
  const store = useStore();
  const navigate = useNavigate();
  const { examId, exam } = useExam();
  const [lastArea, setLastArea] = useState<Area | null>(null);
  const [side, setSide] = useState<Area | null>(null);

  useEffect(() => {
    let alive = true;
    store
      .me()
      .then((me) => alive && setLastArea(me.lastArea))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [store]);

  const begin = () => {
    if (!side) return;
    void navigate(side === 'learn' ? `/train/${examId}` : `/test/${examId}`);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'ArrowLeft') setSide('learn');
      else if (e.key === 'ArrowRight') setSide('test');
      else if (e.key === 'Enter' && side) begin();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const returning = lastArea !== null && side === null;
  const sectionCount = exam.sections.length;
  const notebookCount = exam.sections.reduce((n, s) => n + (notebooks[s.id]?.lessons.length ?? 0), 0);
  const noteCount = exam.sections.filter((s) => notes[s.id]).length;
  const families = familiesFor(examId);
  const half = (which: Area) =>
    ['home-half', which, side === which ? 'chosen' : '', side && side !== which ? 'dimmed' : ''].join(' ');

  return (
    <main className="home">
      <button type="button" className={half('learn')} onClick={() => setSide('learn')} aria-pressed={side === 'learn'} aria-label="Learn">
        <div className="home-glow" />
        <div className="home-body">
          <span style={{ color: 'var(--accent)' }}>
            <Icon name="book" size={56} stroke={1.5} />
          </span>
          <div className="home-word">Learn</div>
          <div className="home-blurb">Section notes with worked examples, then the notebooks and a graded assignment.</div>
          <div className="home-chips">
            <span className="chip">
              {noteCount}/{sectionCount} sections with notes
            </span>
            <span className="chip">{notebookCount} notebooks</span>
          </div>
        </div>
        {returning ? (
          <span className="home-arrow">
            <Icon name="arrow-left" size={72} stroke={1.5} />
          </span>
        ) : null}
      </button>

      <button type="button" className={half('test')} onClick={() => setSide('test')} aria-pressed={side === 'test'} aria-label="Test">
        <div className="home-glow" />
        <div className="home-body">
          <span style={{ color: 'var(--good)' }}>
            <Icon name="timer" size={56} stroke={1.5} />
          </span>
          <div className="home-word">Test</div>
          <div className="home-blurb">Practice with instant feedback, or sit a timed exam at the real length.</div>
          <div className="home-chips">
            <span className="chip">
              {exam.items} items · {exam.minutes} min
            </span>
            <span className="chip">{families} questions</span>
          </div>
        </div>
        {returning ? (
          <span className="home-arrow">
            <Icon name="arrow-right" size={72} stroke={1.5} />
          </span>
        ) : null}
      </button>

      <div className="home-top">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="layers" size={16} stroke={2} />
          </span>
          Databricks DE Prep
        </div>
        <ExamSwitch />
      </div>

      <div className="home-headline">
        <div className="kicker">{lastArea ? 'Welcome back' : `Databricks Certified Data Engineer · ${exams.length} exams`}</div>
        <h1 className="home-h1" key={headline(side, lastArea)}>
          {headline(side, lastArea)}
        </h1>
        {side ? (
          <button type="button" className="btn primary home-begin" onClick={begin}>
            Begin <Icon name="arrow-right" size={18} stroke={2} />
          </button>
        ) : (
          <div className="muted">
            Press <span className="kbd">←</span> or <span className="kbd">→</span> to choose, <span className="kbd">Enter</span> to begin
          </div>
        )}
      </div>
    </main>
  );
}
