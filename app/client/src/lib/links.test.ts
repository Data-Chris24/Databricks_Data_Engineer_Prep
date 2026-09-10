import { describe, expect, it } from 'vitest';

import { workspaceUrl } from './links';

describe('workspaceUrl', () => {
  it('joins host, files root and repo path under #workspace', () => {
    expect(
      workspaceUrl(
        {
          workspaceHost: 'https://example.cloud.databricks.com',
          filesRoot: '/Workspace/Users/sp/.bundle/databricks-de-prep/free/files/',
          contentVersion: 'x',
        },
        'notebooks/lessons/associate/S3/01_cleaning_and_joins',
      ),
    ).toBe(
      'https://example.cloud.databricks.com/#workspace/Workspace/Users/sp/.bundle/databricks-de-prep/free/files/notebooks/lessons/associate/S3/01_cleaning_and_joins',
    );
  });

  it('is null until the app knows where it is deployed', () => {
    expect(workspaceUrl(null, 'x')).toBeNull();
    expect(workspaceUrl({ workspaceHost: 'h', filesRoot: null, contentVersion: 'x' }, 'x')).toBeNull();
  });
});
