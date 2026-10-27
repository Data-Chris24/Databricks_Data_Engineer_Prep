import { describe, expect, it } from 'vitest';

import { existingPaths } from './uc';

const RAW = '/Volumes/workspace/de_prep/raw';

describe('existingPaths', () => {
  it('lists each parent once and treats an unlistable parent as empty', async () => {
    const listed: string[] = [];
    const found = await existingPaths([`${RAW}/s2_teach`, `${RAW}/s4_teach`, `${RAW}/pro_s2/teach`], (dir) => {
      listed.push(dir);
      return Promise.resolve(dir === RAW ? [{ path: `${RAW}/s2_teach/`, isDirectory: true }] : null);
    });
    expect(listed).toEqual([RAW, `${RAW}/pro_s2`]);
    expect(found).toEqual(new Set([`${RAW}/s2_teach`]));
  });

  it('is unknown when nothing could be listed', async () => {
    expect(await existingPaths([`${RAW}/s2_teach`], () => Promise.resolve(null))).toBeNull();
  });
});
