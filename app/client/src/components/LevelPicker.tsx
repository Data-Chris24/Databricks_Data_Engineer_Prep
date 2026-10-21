import { questions } from '../../../shared/content';
import { hasNearMisses } from '../../../shared/optionOrder';
import { TEST_LEVELS, type ExamId, type TestLevel } from '../../../shared/types';
import { LEVEL_NAMES } from '../lib/levels';

const LEVEL_HINTS: Record<TestLevel, string> = {
  standard: 'The questions as written.',
  medium: 'One wrong option per question is a near miss: shaped like the right answer, one detail off.',
  hard: 'Every wrong option is a near miss. You have to find the detail that makes one right.',
};

/** A compact switch for Practice: the three levels as a segmented control, plus coverage. */
export function LevelSwitch({
  exam,
  section,
  value,
  onChange,
}: {
  exam: ExamId;
  section?: string | null;
  value: TestLevel;
  onChange: (level: TestLevel) => void;
}) {
  const pool = questions.filter((q) => q.exam === exam && (!section || q.section === section));
  const ready = pool.filter(hasNearMisses).length;
  return (
    <div className="level-switch">
      <span className="muted">Level</span>
      <div className="seg" role="group" aria-label="Level">
        {TEST_LEVELS.map((l) => (
          <button key={l} type="button" aria-pressed={value === l} title={LEVEL_HINTS[l]} onClick={() => onChange(l)}>
            {LEVEL_NAMES[l]}
          </button>
        ))}
      </div>
      {value !== 'standard' && ready < pool.length ? (
        <span className="muted">
          near misses for {ready} of {pool.length} questions; the rest show as Standard
        </span>
      ) : null}
    </div>
  );
}

/** Choose how tricky the wrong options are (shared/optionOrder.ts). */
export function LevelPicker({
  exam,
  section,
  value,
  onChange,
}: {
  exam: ExamId;
  section?: string | null;
  value: TestLevel;
  onChange: (level: TestLevel) => void;
}) {
  const pool = questions.filter((q) => q.exam === exam && (!section || q.section === section));
  const ready = pool.filter(hasNearMisses).length;
  return (
    <fieldset className="level-picker">
      <legend>Level</legend>
      <div className="level-options" role="radiogroup">
        {TEST_LEVELS.map((l) => (
          <label key={l} className={value === l ? 'on' : ''}>
            <input type="radio" name="level" value={l} checked={value === l} onChange={() => onChange(l)} />
            <b>{LEVEL_NAMES[l]}</b>
            <span>{LEVEL_HINTS[l]}</span>
          </label>
        ))}
      </div>
      {value !== 'standard' ? (
        <p className="muted level-coverage">
          {ready === pool.length
            ? 'Every question here has near misses.'
            : `Near misses are written for ${ready} of ${pool.length} questions so far; the others show as Standard.`}
        </p>
      ) : null}
    </fieldset>
  );
}
