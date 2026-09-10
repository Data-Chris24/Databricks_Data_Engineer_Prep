import { describe, expect, it } from 'vitest';

import { gradeJobKey, isTerminal, parseGradeOutput, settle, taskRunId } from './grading';

describe('gradeJobKey', () => {
  it('matches the bundle job keys', () => {
    expect(gradeJobKey('ASSOC-S3')).toBe('grade_assoc_s3');
    expect(gradeJobKey('PRO-S10')).toBe('grade_pro_s10');
  });
});

describe('parseGradeOutput', () => {
  const good = JSON.stringify({ section: 'ASSOC-S3', passed: false, total: 3, failed: [{ test: 'test_rows', outcome: 'failed', message: 'expected 600' }], tests: [], report_tail: 'x' });
  it('reads the grader JSON out of the notebook output', () => {
    const r = parseGradeOutput({ notebook_output: { result: good } });
    expect(r?.passed).toBe(false);
    expect(r?.failed[0].message).toBe('expected 600');
  });
  it('rejects anything that is not a grader result', () => {
    expect(parseGradeOutput({ notebook_output: { result: 'not json' } })).toBeNull();
    expect(parseGradeOutput({ notebook_output: { result: '{"hello":1}' } })).toBeNull();
    expect(parseGradeOutput({})).toBeNull();
  });
});

describe('settle', () => {
  it('passes or fails from the result, and errors when the grader did not speak', () => {
    const run = { state: { life_cycle_state: 'TERMINATED', result_state: 'SUCCESS' } };
    const pass = JSON.stringify({ section: 'X', passed: true, total: 2, failed: [], tests: [], report_tail: '' });
    expect(settle(run, { notebook_output: { result: pass } }).status).toBe('passed');
    const err = settle({ state: { life_cycle_state: 'INTERNAL_ERROR', state_message: 'cluster died' } }, null);
    expect(err.status).toBe('error');
    expect(err.error).toContain('cluster died');
  });
});

describe('run helpers', () => {
  it('knows terminal states and prefers the task run id', () => {
    expect(isTerminal({ state: { life_cycle_state: 'RUNNING' } })).toBe(false);
    expect(isTerminal({ state: { life_cycle_state: 'TERMINATED' } })).toBe(true);
    expect(taskRunId({ tasks: [{ run_id: 42 }] }, 7)).toBe(42);
    expect(taskRunId({}, 7)).toBe(7);
  });
});
