import { useLocation, useNavigate } from 'react-router';

import { exams } from '../../../shared/content';
import { useExam } from '../lib/exam';

/** Associate / Professional. Stays on the same area when the exam changes. */
export function ExamSwitch() {
  const { examId, setExamId } = useExam();
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <div className="seg" role="group" aria-label="Exam">
      {exams.map((e) => (
        <button
          key={e.id}
          type="button"
          aria-pressed={e.id === examId}
          onClick={() => {
            setExamId(e.id);
            const m = /^\/(train|test)\/(associate|professional)/.exec(location.pathname);
            if (m) void navigate(`/${m[1]}/${e.id}`);
          }}
        >
          {e.short}
        </button>
      ))}
    </div>
  );
}
