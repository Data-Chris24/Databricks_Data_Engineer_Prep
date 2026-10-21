import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/content', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../shared/content')>()),
  visuals: { 'job-dag': '<p>diagram</p>' },
}));

import { Markdown, urlTransform } from '../lib/markdown';
import { parseVisualSrc } from './Visual';

describe('parseVisualSrc', () => {
  it('reads the name and an optional starting height, clamped', () => {
    expect(parseVisualSrc('visual:job-dag')).toEqual({ name: 'job-dag', height: 420 });
    expect(parseVisualSrc('visual:job-dag?h=560')).toEqual({ name: 'job-dag', height: 560 });
    expect(parseVisualSrc('visual:job-dag?h=5')).toEqual({ name: 'job-dag', height: 160 });
    expect(parseVisualSrc('visual:Job_DAG')).toBeNull();
    expect(parseVisualSrc('https://example.com/x.png')).toBeNull();
  });
});

describe('visuals in notes', () => {
  it('keeps visual: sources and still sanitises others', () => {
    expect(urlTransform('visual:job-dag')).toBe('visual:job-dag');
    expect(urlTransform('javascript:alert(1)')).toBe('');
  });

  it('renders a sandboxed frame with a caption, outside any paragraph', () => {
    const html = renderToStaticMarkup(<Markdown source={'Before.\n\n![Fail a task](visual:job-dag)\n\nAfter.'} />);
    expect(html).toContain('<figure class="visual">');
    expect(html).toContain('sandbox="allow-scripts"');
    expect(html).not.toContain('allow-same-origin');
    expect(html).toContain('<figcaption>Fail a task</figcaption>');
    expect(html).not.toMatch(/<p>\s*<figure/);
  });

  it('says so when a visual is missing instead of rendering an empty frame', () => {
    const html = renderToStaticMarkup(<Markdown source={'![x](visual:nope)'} />);
    expect(html).toContain('diagram unavailable');
    expect(html).not.toContain('<iframe');
  });
});
