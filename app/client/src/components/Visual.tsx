import { useEffect, useRef, useState } from 'react';

import { visuals } from '../../../shared/content';

/**
 * Appended to every visual: reports the document's height so the frame can fit
 * its content without a scrollbar. The frame is sandboxed without
 * allow-same-origin, so this message is the only way out of it.
 */
const SIZE_REPORTER = `<script>
(function () {
  // Measure the body, not the document: the document is never shorter than the
  // frame, so its height could grow but never shrink back.
  function report() {
    var b = document.body;
    if (!b) return;
    var cs = getComputedStyle(b);
    var h = Math.ceil(b.getBoundingClientRect().bottom + parseFloat(cs.marginBottom || '0'));
    parent.postMessage({ type: 'de-prep-visual-height', height: h }, '*');
  }
  new ResizeObserver(report).observe(document.body || document.documentElement);
  window.addEventListener('load', report);
  report();
})();
</script>`;

const MIN_HEIGHT = 160;
const MAX_HEIGHT = 1600;

/** Parse `visual:name` or `visual:name?h=520` into the name and a starting height. */
export function parseVisualSrc(src: string): { name: string; height: number } | null {
  const m = /^visual:([a-z0-9]+(?:-[a-z0-9]+)*)(?:\?h=(\d+))?$/.exec(src);
  if (!m) return null;
  const h = m[2] ? Number(m[2]) : 420;
  return { name: m[1], height: Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, h)) };
}

/** An interactive diagram from content/visuals/, embedded in a note. */
export function Visual({ src, caption }: { src: string; caption: string }) {
  const parsed = parseVisualSrc(src);
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(parsed?.height ?? 420);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.source !== frame.current?.contentWindow) return;
      const data = e.data as { type?: unknown; height?: unknown };
      if (data?.type !== 'de-prep-visual-height' || typeof data.height !== 'number') return;
      setHeight(Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, data.height)));
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  const html = parsed ? visuals[parsed.name] : undefined;
  if (!parsed || html === undefined) {
    return <span className="visual-missing">[diagram unavailable: {src}]</span>;
  }

  return (
    <figure className="visual">
      <iframe
        ref={frame}
        title={caption || parsed.name}
        sandbox="allow-scripts"
        srcDoc={html + SIZE_REPORTER}
        style={{ height }}
        loading="lazy"
      />
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  );
}
