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
  header?: React.ReactNode;
  children?: React.ReactNode;
}

export function QuestionCard({ question: q, mode, chosen = null, revealed = false, onChoose, header, children }: QuestionCardProps) {
  const keys = Object.keys(q.options) as OptionKey[];
  const disabled = mode === 'review' || (mode === 'practice' && revealed);
  return (
    <div className="qcard">
      <div className="qmeta">
        {header}
        {mode !== 'test' ? (
          <>
            {q.objectives.map((o) => (
              <span key={o} className="chip obj">
                {o}
              </span>
            ))}
            <span className="chip">{q.difficulty}</span>
            {q.provenance === 'official-sample' ? <span className="chip">official sample</span> : null}
          </>
        ) : null}
      </div>
      <p className="stem">{q.stem}</p>
      {q.code ? <pre className="qcode">{q.code}</pre> : null}
      <div className="opts">
        {keys.map((k) => {
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
              <span className={`key${!revealed && mode !== 'review' ? ' hot' : ''}`}>{k}</span>
              <span>{q.options[k]}</span>
            </button>
          );
        })}
      </div>
      {children}
    </div>
  );
}

export function Explanation({ question: q, chosen }: { question: Question; chosen: OptionKey | null }) {
  const ok = chosen === q.correct;
  const wrongs = (Object.entries(q.why) as [OptionKey, string][]).filter(([k]) => k !== q.correct);
  return (
    <div className="feedback">
      <div className={`verdict ${ok ? 'ok' : 'no'}`}>
        {ok ? 'Correct' : chosen ? `Not quite — the answer is ${q.correct}` : `No answer — the answer is ${q.correct}`}
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
                <dt style={chosen === k ? { fontWeight: 700 } : undefined}>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </div>
  );
}
