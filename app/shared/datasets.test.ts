import { describe, expect, it } from 'vitest';

import { datasetStatus, type RunSummary } from './datasets';

const run = (over: Partial<RunSummary>): RunSummary => ({ runId: 1, lifeCycle: 'TERMINATED', result: 'SUCCESS', message: null, startTime: 1000, endTime: 2000, ...over });

describe('datasetStatus', () => {
  it('is missing when the generate job has never run', () => {
    expect(datasetStatus('X-S1', []).status).toBe('missing');
  });
  it('is unconfigured when no job is bound', () => {
    expect(datasetStatus('X-S1', [], false).status).toBe('unconfigured');
  });
  it('is ready once any run succeeded, even after a later failure', () => {
    const s = datasetStatus('X-S1', [run({ runId: 1 }), run({ runId: 2, startTime: 5000, result: 'FAILED', message: 'boom' })]);
    expect(s.status).toBe('ready');
    expect(s.runId).toBe(1);
    expect(s.finishedAt).toBe('1970-01-01T00:00:02.000Z');
  });
  it('is preparing while a run is active, whatever the history', () => {
    const s = datasetStatus('X-S1', [run({ runId: 1 }), run({ runId: 3, startTime: 9000, lifeCycle: 'RUNNING', result: null, endTime: null })]);
    expect(s.status).toBe('preparing');
    expect(s.runId).toBe(3);
  });
  it('is failed when every completed run failed', () => {
    const s = datasetStatus('X-S1', [run({ result: 'FAILED', message: 'notebook raised' })]);
    expect(s).toMatchObject({ status: 'failed', error: 'notebook raised' });
  });
});
