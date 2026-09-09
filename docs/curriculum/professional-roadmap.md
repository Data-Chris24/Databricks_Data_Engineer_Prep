# Professional study roadmap

A study order for the **Databricks Certified Data Engineer Professional** exam
(59 items, 120 minutes, guide version 2026-07-03).

Full objective list:
[professional-objectives.md](../exam-guides/professional-objectives.md).

---

## Before you start

The Professional exam assumes the Associate material. It isn't a formal
prerequisite, but the objectives don't re-teach Delta, Unity Catalog or the
medallion architecture — they build on them. Databricks recommends roughly **a
year of hands-on data engineering** on the platform.

If the Associate content feels shaky, do that first. This exam is harder in kind,
not just in degree: it asks you to *diagnose* and *choose between trade-offs*
rather than recall.

> **On the weightings:** the Professional guide PDF lists its sections *without*
> percentages. The figures below come from the Databricks certification web page,
> so treat them as indicative rather than quoted.

---

## Where the marks are

| Section | Weight | Roughly this many of 59 |
| --- | --- | --- |
| 1 · Developing Code for Data Processing (Python + SQL) | **22%** | ~13 |
| 6 · Cost & Performance Optimization | **13%** | ~8 |
| 3 · Data Transformation, Cleansing, Quality | 10% | ~6 |
| 5 · Monitoring and Alerting | 10% | ~6 |
| 7 · Data Security and Compliance | 10% | ~6 |
| 9 · Debugging and Deploying | 10% | ~6 |
| 2 · Data Ingestion & Acquisition | 7% | ~4 |
| 8 · Data Governance | 7% | ~4 |
| 10 · Data Modeling | 6% | ~4 |
| 4 · Data Sharing and Federation | 5% | ~3 |

Section 1 alone is **more than a fifth of the exam** — over twice any other
section. Start there and give it the most time.

---

## Suggested order

### 1. Code, pipelines and testing (Section 1, 22%)

The centre of gravity. Modular Python structured for bundles, dependency
management, Pandas/Python UDFs, Lakeflow Spark Declarative Pipelines with Auto
Loader, AUTO CDC (formerly APPLY CHANGES), control-flow operators, and **testing
with `assertDataFrameEqual` / `assertSchemaEqual` / `DataFrame.transform`**.

Two things reliably show up:

- **Streaming tables vs materialized views** — know the trade-off cold.
- **Structured Streaming vs Declarative Pipelines** — when each is the right tool.

> The grading harness in this repo is built from exactly the testing APIs
> `PRO-S1-O11` examines. Read `notebooks/assignments/*/tests/` — it's a worked
> example of a testable objective.

### 2. Ingestion and transformation (Sections 2 + 3, 17%)

Formats (Delta, Parquet, ORC, AVRO, JSON, CSV, XML, binary), message-bus and cloud
storage sources, append-only batch + streaming pipelines, then window functions,
advanced joins, and **quarantining bad data**.

The quarantine pattern is worth real practice — it recurs, and it's the kind of
thing that's obvious once built and vague if only read about.

### 3. Optimization (Section 6, 13%)

The second-biggest section. Liquid Clustering, deletion vectors, data skipping and
file pruning, Change Data Feed, and reading a query profile to find bad skipping,
bad join types and shuffles.

Know **why Liquid Clustering supersedes partitioning + ZORDER** (also `PRO-S10-O3`).
It's a genuine shift in platform guidance and is tested as such.

### 4. Modeling (Section 10, 6%)

Small, and it pairs naturally with optimization: Delta data models, Liquid
Clustering over partitioning, and dimensional modeling for analytics.

### 5. Monitoring, alerting and debugging (Sections 5 + 9, 20%)

Together a fifth of the exam. System tables for cost/audit/utilization, Query
Profiler and Spark UI, pipeline event logs, SQL Alerts, job notifications — then
**job repair with parameter overrides**, and deploying via bundles and Git folders.

> Some of this is limited on Free Edition — cluster logs don't exist without
> clusters, and system table availability needs checking. See the
> [constraints doc](../free-edition-constraints.md) and the
> [optional classic track](../optional-classic-track.md).

### 6. Security, compliance and governance (Sections 7 + 8, 17%)

ACLs and least privilege, row filters and column masks, and
**anonymization vs pseudonymization** — hashing, tokenization, suppression,
generalization. Then PII-masking pipelines, retention-compliant purging, metadata
for discoverability, and UC permission inheritance.

The distinction between anonymization (irreversible) and pseudonymization
(reversible with a key) is precise, and questions exploit imprecision about it.

### 7. Sharing and federation (Section 4, 5%)

Smallest section, so last. Delta Sharing D2D and D2O, Lakehouse Federation.

> Hard to fully practise solo — D2D needs a second party. You can still create
> shares and recipients and inspect what's produced.

---

## Before you book

- Re-check the guide version against [SOURCES.md](../exam-guides/SOURCES.md).
- Take a timed mock at real shape: **59 items, 120 minutes**.
- The exam expects **Python and SQL**, and no test aids — including no API
  documentation. Syntax you'd normally look up needs to be in your head.
- Expect to *diagnose*. Many questions describe a symptom — inconsistent microbatch
  times, a stage reading 5 GB while its peers read 400 MB — and ask what to change.
  Practise reading the evidence, not just recalling features.
