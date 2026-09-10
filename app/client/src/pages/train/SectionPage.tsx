import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';

import { notebooks, notes, questionsFor, sectionById } from '../../../../shared/content';
import type { AppConfig, ProgressRow } from '../../../../shared/types';
import { GradingPanel } from '../../components/GradingPanel';
import { Icon } from '../../components/Icon';
import { useExam } from '../../lib/exam';
import { workspaceUrl } from '../../lib/links';
import { Markdown } from '../../lib/markdown';
import { useStore } from '../../lib/store';

const TOUCH_DELAY_MS = 1500;

export function SectionPage() {
  const store = useStore();
  const navigate = useNavigate();
  const { examId, exam } = useExam();
  const { sectionId = '' } = useParams();
  const section = sectionById(sectionId);
  const note = notes[sectionId];
  const nbs = notebooks[sectionId];

  const [config, setConfig] = useState<AppConfig | null>(null);
  const [progress, setProgress] = useState<ProgressRow | null>(null);
  const [activeAnchor, setActiveAnchor] = useState<string | null>(null);
  const [scrollPct, setScrollPct] = useState(0);
  const pending = useRef<{ anchor?: string; scrollPct?: number }>({});
  const timer = useRef<number | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const toc = useMemo(() => {
    if (!note) return [];
    const main = note.toc.map((e) => ({ ...e, sub: false }));
    const subs = note.subpages.flatMap((p) => [
      { level: 2 as const, text: p.title, anchor: `${p.slug}--title`, objective_ids: p.objective_ids, sub: true },
      ...p.toc.filter((e) => e.level === 2).map((e) => ({ ...e, level: 3 as const, sub: true })),
    ]);
    return [...main, ...subs];
  }, [note]);

  useEffect(() => {
    store.config().then(setConfig).catch(() => {});
  }, [store]);

  // Mark the section visited on arrival and restore the last position.
  useEffect(() => {
    if (!section) return;
    let alive = true;
    store
      .touchSection(examId, section.id, {})
      .then((p) => {
        if (!alive) return;
        setProgress(p);
        const hash = window.location.hash.slice(1);
        const target = hash || p.lastAnchor;
        if (target) {
          requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView({ block: 'start' }));
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [store, examId, section]);

  const flush = () => {
    if (!section) return;
    const patch = pending.current;
    pending.current = {};
    if (patch.anchor === undefined && patch.scrollPct === undefined) return;
    store.touchSection(examId, section.id, patch).then(setProgress).catch(() => {});
  };
  const queue = (patch: { anchor?: string; scrollPct?: number }) => {
    pending.current = { ...pending.current, ...patch };
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(flush, TOUCH_DELAY_MS);
  };
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
      flush();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [section?.id],
  );

  // Track which heading is in view and how far down the page the reader is.
  useEffect(() => {
    const root = contentRef.current;
    if (!root || !note) return;
    const headings = Array.from(root.querySelectorAll<HTMLElement>('h2[id], h3[id], h1[id]'));
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) {
          const id = (visible[0].target as HTMLElement).id;
          setActiveAnchor(id);
          queue({ anchor: id });
        }
      },
      { rootMargin: '-80px 0px -70% 0px', threshold: 0 },
    );
    headings.forEach((h) => io.observe(h));

    const onScroll = () => {
      const rect = root.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const pct = total <= 0 ? 100 : Math.round(Math.min(100, Math.max(0, (-rect.top / total) * 100)));
      setScrollPct(pct);
      queue({ scrollPct: pct });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => {
      io.disconnect();
      window.removeEventListener('scroll', onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note]);

  // Reaching the end of the page (for a second) completes the section.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !section || progress?.completed) return;
    let seenAt: number | null = null;
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        seenAt = Date.now();
        window.setTimeout(() => {
          if (seenAt && Date.now() - seenAt >= 1000) {
            store.touchSection(examId, section.id, { completed: true }).then(setProgress).catch(() => {});
            io.disconnect();
          }
        }, 1050);
      } else {
        seenAt = null;
      }
    });
    io.observe(el);
    return () => io.disconnect();
  }, [store, examId, section, progress?.completed]);

  if (!section || !exam.sections.some((s) => s.id === section.id)) {
    return (
      <div className="page">
        <div className="card empty">
          <strong>No such section</strong>
          <Link to={`/train/${examId}`}>Back to Learn</Link>
        </div>
      </div>
    );
  }

  const questionCount = questionsFor(examId, section.id).length;
  const toggleComplete = () => {
    void store.touchSection(examId, section.id, { completed: !progress?.completed }).then(setProgress).catch(() => {});
  };

  return (
    <div className="page">
      <div className="row-between" style={{ marginBottom: 22 }}>
        <div className="muted" style={{ fontSize: 13.5 }}>
          <Link to={`/train/${examId}`} style={{ color: 'inherit', textDecoration: 'none' }}>
            Learn
          </Link>{' '}
          / {exam.short} /{' '}
          <span style={{ color: 'var(--ink)', fontWeight: 500 }}>
            S{section.number} · {section.title}
          </span>
        </div>
        <div className="read-progress">
          <div className="bar">
            <div style={{ width: `${scrollPct}%` }} />
          </div>
          <span>
            {scrollPct}% read · {progress ? 'saved' : 'saving'}
          </span>
        </div>
      </div>

      <div className="section-grid">
        <aside className="toc sticky">
          <div className="toc-title">On this page</div>
          {toc.map((e, i) => (
            <a
              key={e.anchor}
              href={`#${e.anchor}`}
              className={[e.level === 3 ? 'l3' : '', activeAnchor === e.anchor ? 'active' : '', e.sub && (i === 0 || !toc[i - 1].sub) ? 'toc-sep' : '']
                .filter(Boolean)
                .join(' ')}
              onClick={(ev) => {
                ev.preventDefault();
                document.getElementById(e.anchor)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
              }}
            >
              {e.text}
            </a>
          ))}
          <a href="#hands-on" className={toc.length ? 'toc-sep' : ''}>
            Hands-on and assignment
          </a>
        </aside>

        <article>
          <div className="kicker">
            Section {section.number} · {section.weight}% of the exam
          </div>
          <h1 className="display">{section.title}</h1>

          {note ? (
            <div ref={contentRef}>
              <div className="note">
                <Markdown source={note.markdown} />
              </div>
              {note.subpages.map((p) => (
                <div key={p.slug} className="note subpage">
                  <div className="subpage-kicker">Also in this section</div>
                  <h1 className="sub-title" id={`${p.slug}--title`}>
                    {p.title}
                  </h1>
                  <Markdown source={p.markdown.replace(/^# .*\n/, '')} anchorPrefix={`${p.slug}--`} />
                </div>
              ))}
            </div>
          ) : (
            <div className="card empty" ref={contentRef}>
              <strong>Notes for this section are coming soon</strong>
              The hands-on notebooks below are ready; the written notes land in a later update.
            </div>
          )}

          <div className="end-block" id="hands-on">
            <div className="rail-title">Hands-on · in your workspace</div>
            {config && !workspaceUrl(config, 'x') ? (
              <div className="notice">
                Notebook links open once the app is deployed with the bundle. Locally, open the paths below in your workspace.
              </div>
            ) : null}
            <div className="nb-grid">
              {(nbs?.lessons ?? []).map((nb, i) => {
                const url = workspaceUrl(config, nb.path);
                const inner = (
                  <>
                    <span className="nb-num">{String(i + 1).padStart(2, '0')}</span>
                    <span className="nb-title">{nb.title}</span>
                    <span className="nb-open">
                      {url ? 'Open notebook' : nb.path} {url ? <Icon name="external" size={12} stroke={2} /> : null}
                    </span>
                  </>
                );
                return url ? (
                  <a key={nb.path} className="nb-card" href={url} target="_blank" rel="noopener noreferrer">
                    {inner}
                  </a>
                ) : (
                  <div key={nb.path} className="nb-card">
                    {inner}
                  </div>
                );
              })}
            </div>

            {nbs?.assignment ? (
              <div className="assignment-band">
                <div>
                  <div className="title">Then the assignment, on a dataset the lesson code will not survive</div>
                  <div className="sub">
                    {nbs.assignment.notebook ? 'Starter notebook, task and output contract inside.' : 'Read the task in the README, then build it in your own notebook.'}
                    {' '}Then come back here and grade it.
                  </div>
                </div>
                {(() => {
                  const target = nbs.assignment.notebook ?? nbs.assignment.readme;
                  const url = target ? workspaceUrl(config, target) : null;
                  return url ? (
                    <a className="btn" href={url} target="_blank" rel="noopener noreferrer">
                      Open assignment <Icon name="external" size={14} stroke={2.2} />
                    </a>
                  ) : (
                    <span className="sub">{target}</span>
                  );
                })()}
              </div>
            ) : null}

            {nbs?.assignment ? <GradingPanel sectionId={section.id} gradeJob={nbs.assignment.grade_job} /> : null}

            <div className="end-actions">
              <button
                type="button"
                className="btn primary"
                onClick={() => void navigate(`/test/${examId}/practice?section=${section.id}`)}
                disabled={questionCount === 0}
              >
                Practice this section · {questionCount} question{questionCount === 1 ? '' : 's'}
              </button>
              <button type="button" className={`btn ${progress?.completed ? 'good' : 'ghost'}`} onClick={toggleComplete}>
                {progress?.completed ? (
                  <>
                    <Icon name="check" size={14} stroke={2.5} /> Marked complete
                  </>
                ) : (
                  'Mark complete'
                )}
              </button>
              <span className="muted">Completes automatically when you reach the end.</span>
            </div>
            <div ref={sentinelRef} style={{ height: 1 }} aria-hidden="true" />
          </div>
        </article>
      </div>
    </div>
  );
}
