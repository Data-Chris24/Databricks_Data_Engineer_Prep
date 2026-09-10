import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';

import { ExamProvider } from '../lib/exam';
import { MemoryStore, StoreContext } from '../lib/store';
import { headline, Home } from './Home';

describe('home headline', () => {
  it('asks how to begin on a first visit', () => {
    expect(headline(null, null)).toBe('How would you like to begin?');
  });
  it('offers to continue the last area on a return visit', () => {
    expect(headline(null, 'learn')).toBe('Continue learning Databricks Data Engineering skills?');
    expect(headline(null, 'test')).toBe('Continue testing Databricks Data Engineering skills?');
  });
  it('confirms the chosen side, whatever the history', () => {
    expect(headline('learn', null)).toBe("Let's get started learning Databricks Data Engineering!");
    expect(headline('test', 'learn')).toBe("Let's get started testing Databricks Data Engineering!");
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
    expect(html).not.toContain('Begin');
  });
});
