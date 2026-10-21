import { Link, useParams, useSearchParams } from 'react-router';

import { notes, questionById } from '../../../../shared/content';
import { objectiveAnchor } from '../../../../shared/reviewSuggestions';
import { Explanation, QuestionCard } from '../../components/QuestionCard';
import { ordersForAttempt } from '../../lib/options';
import { LEVEL_NAMES } from '../../lib/levels';
import { useScored } from './Score';

type Filter = 'all' | 'correct' | 'wrong';

export function Review() {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const filter = (params.get('filter') as Filter) || 'all';
  const { attempt, score, error } = useScored(id);

  if (error) return <div className="page page-narrow"><div className="error-banner">{error}</div></div>;
  if (!attempt || !score) return <div className="page page-narrow"><div className="card empty">Loading…</div></div>;

  const orders = ordersForAttempt(attempt);
  // An objective id names its section (ASSOC-S2-O3 -> ASSOC-S2), which may not be the question's.
  const noteLink = (objectiveId: string) => {
    const sectionId = objectiveId.replace(/-O\d+$/, '');
    const anchor = objectiveAnchor(notes[sectionId], objectiveId);
    return anchor ? `/train/${attempt.exam}/${sectionId}#${anchor}` : null;
  };
  const rows = score.perQuestion.map((p, i) => ({ ...p, n: i + 1 }));
  const shown = rows.filter((r) => (filter === 'all' ? true : filter === 'correct' ? r.isCorrect : !r.isCorrect));
  const wrong = rows.filter((r) => !r.isCorrect).length;

  return (
    <div className="page page-narrow">
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div>
          <div className="kicker">
            Review · {LEVEL_NAMES[attempt.level]} · {score.scoreCorrect}/{score.scoreTotal} correct
          </div>
          <h1 className="display" style={{ marginBottom: 6 }}>
            Every question, with the answer
          </h1>
        </div>
        <Link to={`/test/attempt/${id}/score`} className="btn ghost sm">
          Back to score
        </Link>
      </div>

      <div className="filter-tabs" role="group" aria-label="Filter">
        {(
          [
            ['all', `All · ${rows.length}`],
            ['wrong', `Wrong · ${wrong}`],
            ['correct', `Correct · ${rows.length - wrong}`],
          ] as const
        ).map(([f, label]) => (
          <button key={f} type="button" aria-pressed={filter === f} onClick={() => setParams(f === 'all' ? {} : { filter: f })}>
            {label}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <div className="card empty">
          <strong>{filter === 'wrong' ? 'Nothing wrong here' : 'Nothing to show'}</strong>
          {filter === 'wrong' ? 'A clean sheet. Try a harder section in Practice.' : 'Switch the filter.'}
        </div>
      ) : (
        <div className="review-list">
          {shown.map((r) => {
            const q = questionById(r.id);
            if (!q) return null;
            return (
              <QuestionCard
                key={r.id}
                question={q}
                mode="review"
                order={orders[q.id]}
                objectiveHref={noteLink}
                chosen={r.given}
                revealed
                header={
                  <span className={`chip ${r.isCorrect ? '' : ''}`} style={{ color: r.isCorrect ? 'var(--good)' : 'var(--bad)', borderColor: 'currentColor' }}>
                    #{r.n} · {r.isCorrect ? 'correct' : r.given ? 'wrong' : 'no answer'}
                  </span>
                }
              >
                <Explanation question={q} chosen={r.given} order={orders[q.id]} />
              </QuestionCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
