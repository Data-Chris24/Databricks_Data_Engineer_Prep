import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import { exams, isExamId } from '../../../shared/content';
import type { Exam, ExamId } from '../../../shared/types';

const KEY = 'de-prep.exam';

interface ExamContextValue {
  examId: ExamId;
  exam: Exam;
  setExamId: (id: ExamId) => void;
}

const ExamContext = createContext<ExamContextValue | null>(null);

function readStored(): ExamId {
  try {
    const v = localStorage.getItem(KEY);
    if (v && isExamId(v)) return v;
  } catch {
    /* storage unavailable */
  }
  return 'associate';
}

export function ExamProvider({ children, initial }: { children: ReactNode; initial?: ExamId }) {
  const [examId, setId] = useState<ExamId>(initial ?? readStored);
  const setExamId = useCallback((id: ExamId) => {
    setId(id);
    try {
      localStorage.setItem(KEY, id);
    } catch {
      /* fine */
    }
  }, []);
  const value = useMemo<ExamContextValue>(() => {
    const exam = exams.find((e) => e.id === examId) ?? exams[0];
    return { examId, exam, setExamId };
  }, [examId, setExamId]);
  return <ExamContext.Provider value={value}>{children}</ExamContext.Provider>;
}

export function useExam(): ExamContextValue {
  const v = useContext(ExamContext);
  if (!v) throw new Error('ExamProvider missing');
  return v;
}
