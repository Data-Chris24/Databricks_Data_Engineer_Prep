import { describe, expect, it } from 'vitest';

import { type DatasetRunRow, fromRow, settleRun } from './datasets';

const row = (over: Partial<DatasetRunRow>): DatasetRunRow => ({ sectionId: 'X-S1', runId: 7, status: 'succeeded', startedAt: '2026-09-15T10:00:00Z', finishedAt: '2026-09-15T10:01:00Z', error: null, ...over });

describe('fromRow', () => {
  it('is missing with no recorded run, unconfigured with no job', () => {
    expect(fromRow('X-S1', null).status).toBe('missing');
    expect(fromRow('X-S1', null, false).status).toBe('unconfigured');
  });
  it('maps recorded statuses', () => {
    expect(fromRow('X-S1', row({})).status).toBe('ready');
    expect(fromRow('X-S1', row({ status: 'queued', finishedAt: null })).status).toBe('preparing');
    expect(fromRow('X-S1', row({ status: 'running', finishedAt: null })).status).toBe('preparing');
    expect(fromRow('X-S1', row({ status: 'failed', error: 'boom' }))).toMatchObject({ status: 'failed', error: 'boom', runId: 7 });
  });
});

describe('settleRun', () => {
  it('succeeds only on SUCCESS and keeps the job message otherwise', () => {
    expect(settleRun('SUCCESS', null)).toEqual({ status: 'succeeded', error: null });
    expect(settleRun('FAILED', 'notebook raised')).toEqual({ status: 'failed', error: 'notebook raised' });
    expect(settleRun('CANCELED', '')).toEqual({ status: 'failed', error: 'CANCELED' });
    expect(settleRun(null, null)).toEqual({ status: 'failed', error: 'the generate job failed' });
  });
});
