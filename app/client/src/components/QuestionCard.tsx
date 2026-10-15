import { Link } from 'react-router';

import { LABELS, labelFor, type OptionOrder } from '../../../shared/optionOrder';
import type { OptionKey, Question } from '../../../shared/types';

export type CardMode = 'practice' | 'test' | 'review';

export interface QuestionCardProps {
  question: Question;
  mode: CardMode;
  /** The learner's choice, if any. */
  chosen?: OptionKey | null;
  /** Whether to colour the correct/wrong answers (practice after answering; review always). */
  revealed?: boolean;
  onChoose?: (key: OptionKey) => void;
  /** Stored keys in the order to show them (shared/optionOrder.ts); stored order when absent. */
  order?: OptionOrder;
  /** Where an objective chip links to, e.g. its heading in the section note. */
  objectiveHref?: (objectiveId: string) => string | null;
  header?: React.ReactNode;
  children?: React.ReactNode;
}

export function QuestionCard({
  question: q,
  mode,
  chosen = null,
  revealed = false,
  onChoose,
  order,
  objectiveHref,
  header,
  children,
}: QuestionCardProps) {
  const keys = order ?? (Object.keys(q.options) as OptionKey[]);
  const disabled = mode === 'review' || (mode === 'practice' && revealed);
  return (
    <div className="qcard">
      <div className="qmeta">
        {header}
        {mode !== 'test' ? (
          <>
            {q.objectives.map((o) => {
              const href = objectiveHref?.(o);
              return href ? (
                <Link key={o} to={href} className="chip obj" title="Read this in the section note">
                  {o}
                </Link>
              ) : (
                <span key={o} className="chip obj">
                  {o}
                </span>
              );
            })}
            <span className="chip">{q.difficulty}</span>
            {q.provenance === 'official-sample' ? <span className="chip">official sample</span> : null}
          </>
        ) : null}
      </div>
      <p className="stem">{q.stem}</p>
      {q.code ? <pre className="qcode">{q.code}</pre> : null}
      <div className="opts">
        {keys.map((k, i) => {
          const cls = ['opt'];
          if (revealed) {
            if (k === q.correct) cls.push('correct');
            else if (k === chosen) cls.push('wrong');
          } else if (k === chosen) cls.push('chosen');
          return (
            <button
              key={k}
              type="button"
              className={cls.join(' ')}
              disabled={disabled}
              onClick={() => onChoose?.(k)}
              aria-pressed={k === chosen}
            >
              <span className={`key${!revealed && mode !== 'review' ? ' hot' : ''}`}>{LABELS[i]}</span>
              <span>{q.options[k]}</span>
            </button>
          );
        })}
      </div>
      {children}
    </div>
  );
}

export function Explanation({ question: q, chosen, order }: { question: Question; chosen: OptionKey | null; order?: OptionOrder }) {
  const ok = chosen === q.correct;
  const shown = order ?? (Object.keys(q.options) as OptionKey[]);
  const label = (k: OptionKey) => labelFor(shown, k);
  const wrongs = shown.filter((k) => k !== q.correct && q.why[k]).map((k) => [k, q.why[k] ?? ''] as const);
  return (
    <div className="feedback">
      <div className={`verdict ${ok ? 'ok' : 'no'}`}>
        {ok ? 'Correct' : chosen ? `Not quite — the answer is ${label(q.correct)}` : `No answer — the answer is ${label(q.correct)}`}
      </div>
      <p className="why" style={{ margin: '0 0 12px' }}>
        {q.explanation}
      </p>
      {wrongs.length ? (
        <div className="why">
          <h4>Why the others are wrong</h4>
          <dl>
            {wrongs.map(([k, v]) => (
              <div key={k} style={{ display: 'contents' }}>
                <dt style={chosen === k ? { fontWeight: 700 } : undefined}>{label(k)}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </div>
  );
}
