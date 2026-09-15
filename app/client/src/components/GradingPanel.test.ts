import { describe, expect, it } from 'vitest';

import { checkTitle } from './GradingPanel';

describe('checkTitle', () => {
  it('turns a pytest name into a sentence, keeping any parameter', () => {
    expect(checkTitle('test_detail_is_actionable')).toBe('Detail is actionable');
    expect(checkTitle('test_known_rows[BILL-0042]')).toBe('Known rows (BILL-0042)');
    expect(checkTitle('weird')).toBe('weird');
  });
});
