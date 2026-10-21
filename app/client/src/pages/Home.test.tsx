import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';

import { ExamProvider } from '../lib/exam';
import { MemoryStore, StoreContext } from '../lib/store';
import { headline, Home } from './Home';

describe('home headline', () => {
  it('asks how to begin on a first visit', () => {
    expect(headline(null)).toBe('How would you like to begin?');
  });
  it('offers to continue the last area on a return visit', () => {
    expect(headline('learn')).toBe('Continue learning Databricks Data Engineering skills?');
    expect(headline('test')).toBe('Continue testing Databricks Data Engineering skills?');
  });
});

describe('<Home />', () => {
  it('renders the two halves and the opening question', () => {
    const html = renderToStaticMarkup(
      <StoreContext.Provider value={new MemoryStore()}>
        <ExamProvider initial="associate">
          <MemoryRouter>
            <Home />
          </MemoryRouter>
        </ExamProvider>
      </StoreContext.Provider>,
    );
    expect(html).toContain('How would you like to begin?');
    expect(html).toContain('aria-label="Learn"');
    expect(html).toContain('aria-label="Test"');
    expect(html).toContain('45 items · 90 min');
    // One click goes straight in: no Begin step, no chosen/dimmed state.
    expect(html).not.toContain('Begin');
    expect(html).not.toMatch(/home-half[^>]*aria-pressed/);
  });
});

describe('reset notice', () => {
  it('describes the running reset, then its result', async () => {
    const { resetNoticeText } = await import('./train/resetNotice');
    expect(resetNoticeText(7, false)).toBe(
      'Resetting 7 assignments: notebooks back to their starters, output tables being dropped (about a minute).',
    );
    expect(resetNoticeText(1, true)).toBe('1 assignment reset: notebooks are back to their starters and the output tables are gone.');
  });
});
