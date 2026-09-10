import bash from 'highlight.js/lib/languages/bash';
import python from 'highlight.js/lib/languages/python';
import sql from 'highlight.js/lib/languages/sql';
import yaml from 'highlight.js/lib/languages/yaml';
import { isValidElement, useState, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import rehypeSlug from 'rehype-slug';
import remarkGfm from 'remark-gfm';

import { Icon } from '../components/Icon';

const OBJECTIVE_RE = /\b(?:ASSOC|PRO)-S\d+-O\d+\b/g;

/** Plain text of a React subtree, the way the browser would read a heading. */
export function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return '';
}

/** Split "Joins — ASSOC-S3-O2, ASSOC-S3-O3" into a label and its objective chips. */
export function splitHeading(text: string): { label: string; objectives: string[] } {
  const objectives = text.match(OBJECTIVE_RE) ?? [];
  const label = text
    .replace(OBJECTIVE_RE, '')
    .replace(/\s+—\s*[,\s]*$/, '')
    .replace(/[,\s]+$/, '')
    .trim();
  return { label, objectives };
}

function Heading({ level, children, ...rest }: { level: 2 | 3; children?: ReactNode; id?: string }) {
  const { label, objectives } = splitHeading(textOf(children));
  const Tag = level === 2 ? 'h2' : 'h3';
  return (
    <Tag id={rest.id}>
      <span>{label}</span>
      {objectives.map((o) => (
        <span key={o} className="chip obj">
          {o}
        </span>
      ))}
    </Tag>
  );
}

function classNameOf(node: ReactNode): string {
  if (!isValidElement(node)) return '';
  const props = node.props as { className?: unknown };
  return typeof props.className === 'string' ? props.className : '';
}

function Pre({ children }: { children?: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const code: ReactNode = Array.isArray(children) ? (children[0] as ReactNode) : children;
  const lang = /language-([\w-]+)/.exec(classNameOf(code))?.[1] ?? null;
  const text = textOf(children);
  const copy = () => {
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };
  return (
    <pre>
      <div className="code-tools">
        {lang ? <span className="code-lang">{lang}</span> : null}
        <button type="button" className="code-copy" onClick={copy} aria-label="Copy code">
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      {children}
    </pre>
  );
}

const components: Components = {
  h2: ({ children, id }) => (
    <Heading level={2} id={id}>
      {children}
    </Heading>
  ),
  h3: ({ children, id }) => (
    <Heading level={3} id={id}>
      {children}
    </Heading>
  ),
  blockquote: ({ children }) => (
    <blockquote>
      <Icon name="info" size={20} />
      <div>{children}</div>
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="table-wrap">
      <table>{children}</table>
    </div>
  ),
  pre: ({ children }) => <Pre>{children}</Pre>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

export interface MarkdownProps {
  source: string;
  /** Anchor prefix, so a sub-page rendered under a section cannot collide with it. */
  anchorPrefix?: string;
}

export function Markdown({ source, anchorPrefix = '' }: MarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[
        [rehypeSlug, { prefix: anchorPrefix }],
        [
          rehypeHighlight,
          { languages: { sql, python, yaml, bash }, detect: true, subset: ['sql', 'python', 'yaml', 'bash'] },
        ],
      ]}
      components={components}
    >
      {source}
    </ReactMarkdown>
  );
}
