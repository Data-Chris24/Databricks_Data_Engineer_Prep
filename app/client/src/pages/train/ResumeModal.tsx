import { useState } from 'react';

import { Icon } from '../../components/Icon';

export function ResumeModal({
  sectionLabel,
  onContinue,
  onStartOver,
}: {
  sectionLabel: string;
  onContinue: () => void;
  onStartOver: () => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="resume-title">
      <div className="modal">
        {confirming ? (
          <>
            <h2 id="resume-title">Start over?</h2>
            <p>This clears which sections you have read and completed for this exam. Practice history and test results are kept.</p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn primary"
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  void onStartOver();
                }}
              >
                Yes, start over
              </button>
              <button type="button" className="btn ghost" onClick={() => setConfirming(false)}>
                Keep my progress
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 id="resume-title">Continue where you left off?</h2>
            <p>You were reading {sectionLabel}.</p>
            <div className="modal-actions">
              <button type="button" className="btn primary" onClick={onContinue} autoFocus>
                Continue <Icon name="arrow-right" size={16} stroke={2} />
              </button>
              <button type="button" className="btn ghost" onClick={() => setConfirming(true)}>
                Start over
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
