import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';

import { type FlowSection, type LessonDestination, lessonDestination } from '../../../../shared/lessonFlow';
import { useExam } from '../../lib/exam';
import { useStore } from '../../lib/store';

export const PRACTICE_BATCH = 5;

/**
 * After a batch of practice questions: keep going, or back to the lesson.
 * "Back" is decided from progress, not guessed: an unfinished section (no
 * passing grade yet) takes the learner back into it; a finished one moves
 * them on to the next unfinished section.
 */
export function PracticeBreak({ sectionId, answered, onContinue }: { sectionId: string | null; answered: number; onContinue: () => void }) {
  const store = useStore();
  const navigate = useNavigate();
  const { examId, exam } = useExam();
  const [dest, setDest] = useState<LessonDestination | null>(null);

  useEffect(() => {
    let alive = true;
    const sections: FlowSection[] = exam.sections.map((s) => ({ id: s.id, number: s.number, title: s.title }));
    store
      .training(examId)
      .then((t) => {
        if (!alive) return;
        const completed = new Set(Object.values(t.sections).filter((s) => s.completed).map((s) => s.sectionId));
        setDest(lessonDestination(sections, sectionId, completed));
      })
      .catch(() => alive && setDest(lessonDestination(sections, sectionId, new Set())));
    return () => {
      alive = false;
    };
  }, [store, examId, exam, sectionId]);

  const go = () => {
    if (!dest) return;
    void navigate(dest.kind === 'section' ? `/train/${examId}/${dest.section.id}` : `/train/${examId}`);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onContinue();
      else if (e.key === 'Enter' && dest) go();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  });

  const current = exam.sections.find((s) => s.id === sectionId);
  const label = dest
    ? dest.kind === 'home'
      ? dest.why === 'all_done'
        ? 'Every section is complete · back to Learn'
        : 'Back to Learn'
      : dest.why === 'next'
        ? `On to S${dest.section.number} · ${dest.section.title}`
        : `Back to S${dest.section.number} · ${dest.section.title}`
    : 'Back to the lesson';

  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="break-title">
      <div className="modal">
        <div className="kicker">Practice · {current ? `S${current.number}` : exam.short}</div>
        <h2 id="break-title">
          {answered} questions done. Keep going?
        </h2>
        <p className="muted">
          {dest?.kind === 'section' && dest.why === 'next'
            ? `S${current?.number ?? ''} is complete: its assignment passed. The next lesson is waiting.`
            : dest?.kind === 'section'
              ? 'This section is not complete yet: finish its notebooks and pass the assignment to move on.'
              : 'Pick up the lessons whenever you are ready.'}
        </p>
        <div className="modal-actions">
          <button type="button" className="btn primary" onClick={go} disabled={!dest} autoFocus>
            {label}
          </button>
          <button type="button" className="btn ghost" onClick={onContinue}>
            Keep practicing
          </button>
        </div>
        <div className="muted" style={{ marginTop: 10, fontSize: 12.5 }}>
          <span className="kbd">Enter</span> lesson · <span className="kbd">Esc</span> keep practicing
        </div>
      </div>
    </div>
  );
}
