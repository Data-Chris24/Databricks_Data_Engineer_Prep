# Associate study roadmap

A study order for the **Databricks Certified Data Engineer Associate** exam
(45 items, 90 minutes, guide version 2026-05-04).

The full objective list is in
[associate-objectives.md](../exam-guides/associate-objectives.md). This page is
about *sequence* — what to learn when, and where to spend your time.

---

## Where the marks actually are

| Section | Weight | Roughly this many of 45 items |
| --- | --- | --- |
| 3 · Data Transformation and Modeling | **22%** | ~10 |
| 2 · Data Ingestion and Loading | **21%** | ~9 |
| 4 · Working with Lakeflow Jobs | **16%** | ~7 |
| 7 · Governance and Security | **15%** | ~7 |
| 5 · Implementing CI/CD | 10% | ~5 |
| 6 · Troubleshooting, Monitoring, Optimization | 10% | ~5 |
| 1 · Databricks Intelligence Platform | 6% | ~3 |

Sections 2 and 3 are **43% of the exam between them**. If time is short, that's
where it goes.

---

## Suggested order

Not the guide's numbering — the guide is organised by topic, this is organised by
what depends on what.

### 1. Foundations first (Section 1, 6%)

Small section, but everything else assumes it: the Delta Lake transaction log,
Unity Catalog's three-level namespace, and how the compute types differ.

Do this first even though it's only 6%, because a shaky mental model of Delta and
UC makes every later section harder than it needs to be.

> `ASSOC-S1-O2` (compute cost models) can't be practised on Free Edition —
> serverless-only means there's nothing to compare. Read it, and take the
> [optional classic lab](../optional-classic-track.md) if you want it hands-on.

### 2. Ingestion (Section 2, 21%)

`COPY INTO` vs Auto Loader, schema enforcement and evolution, and — the part
that's most often tested — **choosing between ingestion methods** given volume,
frequency and governance requirements.

Get comfortable with schema evolution actually happening. Watching a new column
appear mid-stream is worth more than reading the option name.

### 3. Transformation and modeling (Section 3, 22%)

The biggest section. Bronze → silver → gold, joins, dedup, aggregation, and the
difference between views, materialized views, streaming tables and plain tables.

Know **when each gold-layer object is right**, not just how to write the DDL.
That distinction is where the questions live.

### 4. Orchestration (Section 4, 16%)

Lakeflow Jobs: task dependencies and the DAG, retries, conditional branching and
looping, and trigger types — scheduled, file arrival, table update.

The recurring question shape is *time-based vs data-driven triggering*: pick based
on whether data arrives predictably.

> Free Edition allows **5 concurrent job tasks**. Enough to learn every concept;
> keep your DAGs narrow.

### 5. Governance and security (Section 7, 15%)

Managed vs external tables, `GRANT`/`REVOKE`/`DENY`, the securable hierarchy and
how privileges inherit, then row filters and column masks.

Sitting this one late pays off — by now you've created enough objects for
ownership and inheritance to mean something concrete.

### 6. CI/CD (Section 5, 10%)

Git folders, and Declarative Automation Bundles for promoting the same codebase
across dev/test/prod with per-target overrides.

**This repo is itself a worked example** — read `bundle/` and the GitHub Actions
workflow.

### 7. Troubleshooting and optimization (Section 6, 10%)

Job run history, reading the Spark UI for skew/shuffle/spill, Liquid Clustering
and predictive optimization.

Last, deliberately: diagnosing pipelines is much easier once you've built some.

> `ASSOC-S6-O5` (cluster startup failures, library conflicts, OOM) is theory-only
> on Free Edition — there are no clusters to break. The
> [optional classic lab](../optional-classic-track.md) covers it by deliberately
> breaking things.

---

## Before you book

- Re-check the guide version against
  [SOURCES.md](../exam-guides/SOURCES.md) — Databricks revises these.
- Take a timed mock at real shape: **45 items, 90 minutes**. That's two minutes per
  item; the pacing is worth rehearsing.
- Review your weakest sections *by weighting*. Being shaky on Section 3 costs about
  three times what being shaky on Section 1 costs.
- Note the naming: the guide uses current names (Lakeflow Jobs, Declarative
  Automation Bundles) while much of the material online still says Workflows and
  Asset Bundles. Know both.
