import { useCallback, useEffect, useState } from 'react';

import { gateHint } from '../../../shared/gate';
import type { AppConfig, AssignmentState, SectionNotebooks } from '../../../shared/types';
import { workspaceUrl } from '../lib/links';
import { ApiError, LessonsUnvisitedError, useStore } from '../lib/store';
import { Icon } from './Icon';

/**
 * The assignment step at the end of a section. Locked until every hands-on
 * notebook has been opened from the app; then it sets up the learner's own
 * copy of the starter (or links to the task when a section has no starter yet),
 * and can reset that copy to the starter.
 */
export function AssignmentBand({
  sectionId,
  notebooks,
  config,
  visited,
}: {
  sectionId: string;
  notebooks: SectionNotebooks;
  config: AppConfig | null;
  visited: Set<string>;
}) {
  const store = useStore();
  const [state, setState] = useState<AssignmentState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    store
      .assignment(sectionId)
      .then(setState)
      .catch((e: Error) => setError(e.message));
  }, [store, sectionId]);

  useEffect(() => {
    load();
  }, [load, visited.size]);

  const run = (fn: () => Promise<AssignmentState>) => {
    setBusy(true);
    setError(null);
    fn()
      .then(setState)
      .catch((e: unknown) => {
        if (e instanceof LessonsUnvisitedError) setError(gateHint(e.gate));
        else if (e instanceof ApiError && e.message === 'learner_workspace_not_configured') setError('Your own copy of the notebook can only be created in the deployed app.');
        else setError((e as Error).message);
      })
      .finally(() => setBusy(false));
  };

  const reset = () => {
    if (!window.confirm('Reset your assignment notebook to the starter? Your edits in it will be lost. Grades already recorded are kept.')) return;
    run(() => store.resetAssignment(sectionId));
  };

  const lessons = notebooks.lessons.map((l) => l.path);
  const done = lessons.filter((p) => visited.has(p)).length;
  const ready = state ? state.gate.ready : done === lessons.length;
  const hint = state ? gateHint(state.gate) : gateHint({ ready, done, total: lessons.length, missing: [] });
  const workspacePath = (p: string) => (p.startsWith('/Workspace') ? p : `/Workspace${p}`);
  const copyUrl = state?.notebook && config?.workspaceHost ? `${config.workspaceHost}/#workspace${workspacePath(state.notebook)}` : null;
  const readmeUrl = notebooks.assignment.readme ? workspaceUrl(config, notebooks.assignment.readme) : null;

  let action: React.ReactNode;
  if (!ready) {
    action = (
      <button type="button" className="btn" disabled title={hint} aria-disabled="true">
        Open assignment · {done}/{lessons.length} reviewed
      </button>
    );
  } else if (state?.hasStarters) {
    action = state.provisioned ? (
      <div className="band-actions">
        {copyUrl ? (
          <a className="btn" href={copyUrl} target="_blank" rel="noopener noreferrer">
            Open my assignment <Icon name="external" size={14} stroke={2.2} />
          </a>
        ) : (
          <span className="sub">{state.notebook}</span>
        )}
        <button type="button" className="btn ghost sm band-ghost" onClick={reset} disabled={busy}>
          Reset to starter{state.resetCount ? ` (${state.resetCount})` : ''}
        </button>
      </div>
    ) : (
      <button type="button" className="btn" onClick={() => run(() => store.provisionAssignment(sectionId))} disabled={busy}>
        {busy ? 'Setting up…' : 'Set up my assignment notebook'}
      </button>
    );
  } else if (readmeUrl) {
    action = (
      <a className="btn" href={readmeUrl} target="_blank" rel="noopener noreferrer">
        Read the task <Icon name="external" size={14} stroke={2.2} />
      </a>
    );
  } else {
    action = <span className="sub">No assignment yet</span>;
  }

  return (
    <div className="assignment-band">
      <div>
        <div className="title">Then the assignment, on a dataset the lesson code will not survive</div>
        <div className="sub">
          {!ready
            ? hint
            : state?.hasStarters
              ? state.provisioned
                ? 'Your own copy of the starter, in your workspace folder. Come back here to grade it.'
                : 'You get your own copy of the starter notebook to work in; the deployed one stays untouched.'
              : 'Read the task, build it in your own notebook, then come back here to grade it.'}
          {readmeUrl && state?.hasStarters ? (
            <>
              {' '}
              <a href={readmeUrl} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--code-kw)' }}>
                The task
              </a>
            </>
          ) : null}
        </div>
        {error ? <div className="sub" style={{ color: 'var(--code-kw)', marginTop: 6 }}>{error}</div> : null}
      </div>
      {action}
    </div>
  );
}
