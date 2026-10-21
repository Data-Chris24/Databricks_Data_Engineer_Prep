# Exam Guide Sources

Every objective in this repository traces back to an official Databricks exam
guide. This file records exactly which version was used, where it came from, and
how to check for a newer one.

> Databricks updates these guides whenever the live exam changes. **Re-verify
> before relying on the objective maps for a scheduled exam sitting.**

## Retrieved 2026-09-09

### Data Engineer Associate

| Field | Value |
| --- | --- |
| Guide version | **May 4, 2026** |
| Guide PDF | <https://www.databricks.com/sites/default/files/2026-05/databricks-certified-data-engineer-associate-exam-guide-may-2026-000.pdf> |
| Certification page | <https://www.databricks.com/learn/certification/data-engineer-associate> |
| Scored items | 45 multiple-choice |
| Time limit | 90 minutes |
| Registration fee | USD 200 (plus local tax) |
| Delivery | Online proctored or test center |
| Test aids | None allowed |
| Prerequisite | None required; course attendance and ~6 months hands-on Databricks experience recommended |
| Validity | 2 years |

### Data Engineer Professional

| Field | Value |
| --- | --- |
| Guide version | **July 3, 2026** |
| Guide PDF | <https://www.databricks.com/sites/default/files/2026-07/databricks-certified-data-engineer-professional-exam-guide-july-3-2026.pdf> |
| Certification page | <https://www.databricks.com/learn/certification/data-engineer-professional> |
| Scored items | 59 multiple-choice |
| Time limit | 120 minutes |
| Registration fee | USD 200 (plus local tax) |
| Delivery | Online proctored or test center |
| Test aids | None provided, including API documentation |
| Prerequisite | None required; course attendance and ~1 year hands-on data engineering experience recommended |
| Validity | 2 years |

## Important caveat on Professional weightings

The **Associate** guide PDF states section weightings inline. The **Professional**
guide PDF does *not* — it lists the ten sections without percentages. The
Professional weightings recorded in this repo come from the Databricks
certification web page, not the PDF. They are marked
`weighting_source: certification_page` in
[`content/objectives/professional.yaml`](../../content/objectives/professional.yaml)
so the distinction stays visible.

## How to refresh

1. Open the certification page for the exam. The current guide PDF is linked
   there; the filename encodes the version date.
2. Compare that date against the "Guide version" above.
3. If it changed, download the PDF and extract its text:
   ```bash
   python3 -m venv .venv && .venv/bin/pip install pypdf
   .venv/bin/python -c "
   from pypdf import PdfReader
   print('\n'.join(p.extract_text() for p in PdfReader('guide.pdf').pages))
   "
   ```
   (macOS ships no PDF text extractor; `pypdf` in a throwaway venv is the
   lowest-friction option.)
4. Diff the outline against `content/objectives/*.yaml`, update the YAML and the
   markdown maps, and bump the dates in this file.

## Copyright note

The objective text in this repo is quoted from the Databricks exam guides for
study purposes and is attributed above. The official sample questions carried in
`content/questions/*/official-sample-*.yaml` are the retired questions Databricks
publishes in those same guides. Do not add real exam content — Databricks
certification has an NDA, and braindump material would make this repo
unshareable.
