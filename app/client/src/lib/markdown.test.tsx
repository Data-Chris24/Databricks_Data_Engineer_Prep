import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Markdown, splitHeading } from './markdown';

describe('splitHeading', () => {
  it('separates the label from its objective ids', () => {
    expect(splitHeading('Joins — ASSOC-S3-O2')).toEqual({ label: 'Joins', objectives: ['ASSOC-S3-O2'] });
    expect(splitHeading('JDBC and semi-structured — ASSOC-S2-O5, ASSOC-S2-O7')).toEqual({
      label: 'JDBC and semi-structured',
      objectives: ['ASSOC-S2-O5', 'ASSOC-S2-O7'],
    });
    expect(splitHeading('Plain heading')).toEqual({ label: 'Plain heading', objectives: [] });
  });
});

describe('Markdown', () => {
  it('gives headings the same anchors the build script computes, plus objective chips', () => {
    const html = renderToStaticMarkup(<Markdown source={'## Joins — `ASSOC-S3-O2`\n\ntext'} />);
    expect(html).toContain('id="joins--assoc-s3-o2"');
    expect(html).toContain('class="chip obj">ASSOC-S3-O2');
    expect(html).toContain('<span>Joins</span>');
  });

  it('prefixes anchors for sub-pages', () => {
    const html = renderToStaticMarkup(<Markdown source={'## 1. DELTA_FAILED'} anchorPrefix="errors--" />);
    expect(html).toContain('id="errors--1-delta_failed"');
  });

  it('renders GFM tables inside a scroll wrapper and quotes as callouts', () => {
    const html = renderToStaticMarkup(
      <Markdown source={'| a | b |\n|---|---|\n| 1 | 2 |\n\n> careful'} />,
    );
    expect(html).toContain('class="table-wrap"');
    expect(html).toContain('<th>a</th>');
    expect(html).toContain('<blockquote><svg');
  });

  it('highlights fenced sql and labels the block', () => {
    const html = renderToStaticMarkup(<Markdown source={'```sql\nSELECT 1\n```'} />);
    expect(html).toContain('code-lang">sql');
    expect(html).toContain('hljs-keyword');
  });
});
