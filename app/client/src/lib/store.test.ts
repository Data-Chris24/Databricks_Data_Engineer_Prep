import { describe, expect, it } from 'vitest';

import { AppRestartingError, parseJson } from './store';

describe('parseJson', () => {
  it('parses a JSON body and treats an empty body as no data', () => {
    expect(parseJson(200, '{"a":1}')).toEqual({ a: 1 });
    expect(parseJson(200, '')).toEqual({});
  });
  it('turns the platform start page into a readable error, not a JSON parse failure', () => {
    expect(() => parseJson(503, '<!DOCTYPE html><html>starting</html>')).toThrow(AppRestartingError);
    expect(() => parseJson(200, 'not json at all')).toThrow(AppRestartingError);
    try {
      parseJson(503, '<html/>');
    } catch (e) {
      expect((e as Error).message).toMatch(/restarting/);
    }
  });
});
