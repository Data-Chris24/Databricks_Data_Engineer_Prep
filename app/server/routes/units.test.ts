import { describe, expect, it } from 'vitest';

import { afterRun, failureMessage, planSetup } from './units';

describe('afterRun', () => {
  it('starts the set-up once the other units are clean', () => {
    expect(afterRun({ action: 'setup', phase: 'cleaning_others' }, { ok: true, error: null })).toEqual({ phase: 'setting_up', startSetup: true });
  });
  it('finishes a set-up, a clean-up and a removal', () => {
    for (const [action, phase] of [['setup', 'setting_up'], ['cleanup', 'cleaning'], ['remove', 'removing']] as const) {
      expect(afterRun({ action, phase }, { ok: true, error: null })).toEqual({ phase: 'done', startSetup: false });
    }
  });
  it('never sets up after a failed clean-up', () => {
    expect(afterRun({ action: 'setup', phase: 'cleaning_others' }, { ok: false, error: 'x' })).toEqual({ phase: 'failed', startSetup: false });
  });
});

describe('planSetup', () => {
  it('asks first when other units hold resources, and cleans them once confirmed', () => {
    expect(planSetup(['PRO-S4'], false)).toEqual({ needsConfirm: true, clean: ['PRO-S4'] });
    expect(planSetup(['PRO-S4'], true)).toEqual({ needsConfirm: false, clean: ['PRO-S4'] });
    expect(planSetup([], false)).toEqual({ needsConfirm: false, clean: [] });
  });
});

describe('failureMessage', () => {
  it('prefers the notebook error over the run state', () => {
    expect(failureMessage({ state: { state_message: 'Workload failed' } }, 'RuntimeError: 1 object(s) could not be removed')).toBe('RuntimeError: 1 object(s) could not be removed');
    expect(failureMessage({ state: { state_message: 'Workload failed' } }, null)).toBe('Workload failed');
    expect(failureMessage({}, undefined)).toBe('the job failed');
  });
});
