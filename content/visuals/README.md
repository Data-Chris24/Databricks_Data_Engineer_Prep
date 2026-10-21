# Interactive diagrams

One self-contained HTML file per diagram, named in lowercase kebab case
(`job-dag-repair.html`). `tools/build_app_content.py` puts them in
`app/shared/content/visuals.json`, and a note embeds one on a line of its own:

```markdown
![Fail a task and pick each dependant's run_if](visual:job-dag-repair)
![Same, with a taller starting frame](visual:job-dag-repair?h=560)
```

The alt text becomes the caption and the frame's accessible title. One file can
serve several sections: embed it from each note that needs it.

## The contract

- **Self-contained.** Inline `<style>` and `<script>` only: no CDN, no fonts,
  no images by URL, no `fetch`. The build rejects `src`/`href`/`url()` pointing
  at `//` or `http(s)://`, `@import`, `fetch(`, `XMLHttpRequest` and
  `WebSocket`. Keep it under 200 KB.
- **Sandboxed.** The app renders it in `<iframe sandbox="allow-scripts">` from
  `srcdoc`: scripts run, but there is no access to the app, its storage or
  cookies, and no navigation. Don't use `localStorage` (it throws here); keep
  state in memory.
- **Height.** The app appends a small script that reports the document height,
  so the frame grows to fit. Give `body` a margin of 0 and avoid `100vh`
  layouts. `?h=` sets the height used before the first report (default 420).
- **Width.** The note column is up to 760 px and can be as narrow as a phone.
  Lay out for 320–760 px with no horizontal scroll.
- **Light and dark.** The app follows the system setting, and the frame
  inherits it. Define colours as CSS variables on `:root` and redefine them
  under `@media (prefers-color-scheme: dark)`. Use a transparent `body`
  background so the note shows through.
- **Accessible.** Real `<button>`s with text labels, keyboard operable, and
  state changes announced in text (an `aria-live` line), not by colour alone.
- **Correct.** A diagram is a claim about behaviour, held to the same standard
  as a note: check it on Free Edition or against the current docs, and say in
  the PR which.
