import { useState } from 'react';

import { Icon } from '../../components/Icon';

type Step = 'prompt' | 'confirm';

/**
 * Two jobs: on arrival, offer to continue where the learner left off; and,
 * from there or from the Learn home's own button, start the exam over. Starting
 * over always clears reading progress and notebook visits; the learner chooses
 * whether every assignment is reset too.
 */
export function ResumeModal({
  sectionLabel,
  initialStep = 'prompt',
  onContinue,
  onStartOver,
  onClose,
}: {
  sectionLabel: string | null;
  initialStep?: Step;
  onContinue: () => void;
  onStartOver: (resetAssignments: boolean) => Promise<void>;
  onClose?: () => void;
}) {
  const [step, setStep] = useState<Step>(initialStep);
  const [busy, setBusy] = useState(false);
  const go = (resetAssignments: boolean) => {
    setBusy(true);
    void onStartOver(resetAssignments);
  };
  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="resume-title">
      <div className="modal">
        {step === 'confirm' ? (
          <>
            <h2 id="resume-title">Start this exam over?</h2>
            <p>
              Reading progress and which hands-on notebooks you have opened are cleared either way, so assignments lock again.
              You can also reset every assignment: each notebook copy goes back to its starter, the tables the assignments
              produced are dropped, and their grades are forgotten. Practice history and test results are always kept.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn primary" disabled={busy} onClick={() => go(true)}>
                Start over and reset all assignments
              </button>
              <button type="button" className="btn ghost" disabled={busy} onClick={() => go(false)}>
                Start over, keep my assignments
              </button>
              <button type="button" className="btn ghost" disabled={busy} onClick={() => (initialStep === 'confirm' && onClose ? onClose() : setStep('prompt'))}>
                Cancel
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 id="resume-title">Continue where you left off?</h2>
            <p>{sectionLabel ? `You were reading ${sectionLabel}.` : 'Pick up where you were.'}</p>
            <div className="modal-actions">
              <button type="button" className="btn primary" onClick={onContinue} autoFocus>
                Continue <Icon name="arrow-right" size={16} stroke={2} />
              </button>
              <button type="button" className="btn ghost" onClick={() => setStep('confirm')}>
                Start over
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
