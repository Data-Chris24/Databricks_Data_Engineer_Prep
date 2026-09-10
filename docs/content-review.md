# Content review: depth, links and visuals (September 2026)

A review of all seventeen section notes against the objectives, asking one
question: does each note give a candidate *full* knowledge of the subject, or a
tidy summary of the docs? The verdict is consistent. The notes are strong on
**why** (mental models, traps, the anti-transplant framing) and thin on **what**:
syntax, option names, defaults and the numbers the exam tests. Below is what was
fixed straight away, what each section still needs, and a plan for visuals.

## Fixed in the same change

Factual corrections applied to the notes (and the one lesson notebook and two
questions that repeated them):

| Where | Was | Now |
|---|---|---|
| ASSOC-S1 | "high concurrency with autoscaling" | SQL warehouse with autoscaling; High Concurrency is a retired cluster mode |
| ASSOC-S1 | Serverless listed as a fourth compute type | a variant of the other three, billed per second in use |
| ASSOC-S2 | COPY INTO never re-loads a file | `COPY_OPTIONS ('force' = 'true')` does; `inferSchema` / `mergeSchema` named |
| ASSOC-S2 | "enable `rescuedDataColumn` as routine" | on by default under inference; set it when you supply a schema |
| ASSOC-S3 | `CAST` returns NULL, never raises | depends on ANSI mode; ANSI on (the default) raises `CAST_INVALID_INPUT` |
| ASSOC-S3 | `UNION` deduplicates | in SQL; `df.union()` is positional and never deduplicates |
| ASSOC-S4 | overlapping runs skipped by default | UI-created jobs queue by default; API/bundle jobs skip unless `queue.enabled` |
| ASSOC-S5 | development mode only prefixes names | it also pauses schedules and triggers, caps concurrency, drops the lock |
| ASSOC-S6 | predictive optimization on "managed tables" | managed tables *only*; also collects statistics |
| ASSOC-S7 | DENY never mentioned though the objective lists it | there is no DENY in Unity Catalog; `UNDROP` window is seven days |
| PRO-S1 | `APPLY CHANGES INTO live.` example | `CREATE FLOW ... AS AUTO CDC INTO`, with the SCD type 2 behaviour for late events |
| PRO-S1 | materialized view recomputes "the whole query" | incremental where the query allows; `assertDataFrameEqual` ignores row order by default |
| PRO-S4 | CDF clause "refused on Databricks-managed keys" stated as a rule | labelled as a Free Edition measurement |
| PRO-S5 | "Free Edition exposes few `system.*` schemas" | it exposes them with real rows (verified: `system.billing.usage` returns rows) |
| PRO-S6 | managed tables "get liquid clustering and deletion vectors first" | those work on external tables; managed-only is predictive optimization, `CLUSTER BY AUTO`, `UNDROP` |
| PRO-S7 | notebook ACL names; `current_user_region()` as if built in; "anyone who can alter" drops a mask | correct ACL names per object; labelled as a user function; owner or `MANAGE` |
| PRO-S8 | tags on tables and columns | tags on every securable |
| PRO-S9 | repair re-runs failed tasks "and their dependants" | the dependants that were skipped; successful ones only with `rerun_dependent_tasks` |
| PRO-S10 | `REPLACE WHERE` on a partition column "is a metadata operation" | old files dropped by metadata, new slice still written; clustered tables must read and rewrite |

Every note also gained a **Further reading** footer: official documentation, one
link per topic the section tests, and one to three videos with channel and
length. All 123 distinct documentation links returned 200 and every video was resolved
through YouTube's oEmbed endpoint on 2026-09-10.

## Per-section depth work

Each entry lists what a candidate must know that the note does not yet teach,
then the additions that would close the gap. Sections are ordered by exam weight
within each exam.

### ASSOC-S3 Data Transformation and Modeling (22%)

- Missing: `na.drop` / `na.fill` variants, `to_date` formats, join strategies and
  `broadcast()`, semi and anti joins, `EXCEPT` / `INTERSECT`, `posexplode`,
  `element_at` (1-based) vs `get` (0-based), `collect_set`, the window
  `row_number` idiom the note only alludes to, `describe()` vs `summary()`,
  `spark.default.parallelism` (named in O5), materialized view and streaming
  table syntax with refresh commands, `RELY` on informational keys.
- Add: a **join strategy chooser** (sizes in, strategy and shuffle out); an
  **ANSI mode table** of what raises vs returns null and the `try_*` family; a
  **gold object decision tree** (view / MV / streaming table / table by
  freshness, read-write ratio and source shape); one **constraint vs
  expectation** worked example of the same rule.

### ASSOC-S2 Data Ingestion and Loading (21%)

- Missing: the non-incremental paths the exam contrasts against (UI upload,
  `read_files`, `SELECT * FROM csv.`, CTAS, `INSERT OVERWRITE`, `MERGE` as
  ingestion); COPY INTO transforms and return columns; **directory listing vs
  file notification** (named in O3, absent); the four `schemaEvolutionMode`
  values; `inferColumnTypes`; `includeExistingFiles`; Lakeflow Connect
  connector names and `CREATE CONNECTION`; JDBC partitioned reads; the JSON
  toolkit (`:` paths, `from_json`, `VARIANT`, `explode`).
- Add: **directory listing vs file notification** with the scale cue words; a
  **schema evolution table** (source adds a column / changes a type / sends
  garbage, under each mode); **the five ways to load a file, ranked**; one
  **nested JSON to flat silver row** walkthrough.

### ASSOC-S4 Lakeflow Jobs (16%)

- Missing: the six `run_if` values; If/else and For each mechanics; retry and
  timeout knobs; `taskValues` with `debugValue`; job vs task parameters and
  widgets; task types beyond notebook; shared job clusters; cron with timezone;
  file arrival settings; table update triggers; `run-now` from the CLI.
- Add: a **`run_if` scenario** (A, then B fails and C succeeds, then D) showing
  D's fate under each value; **repair vs rerun vs retry**; **parameters and task
  values end to end**; a **trigger chooser**.

### ASSOC-S7 Governance and Security (15%)

- Missing: external location and storage credential; `SET MANAGED` conversion
  (named in O1); the full privilege list including `BROWSE` and `MANAGE`;
  ownership transfer; `SHOW GRANTS`; the view-owner rule; catalog-workspace
  binding; mask and filter syntax and `information_schema.column_masks`; ABAC
  policy syntax and governed tags.
- Add: **the traversal puzzle three ways** (table, schema, catalog grant, each
  with `SHOW GRANTS` and the error); **view vs dynamic view vs mask vs ABAC** for
  one requirement; **managed to external lifecycle**; **ABAC in one policy**.

### ASSOC-S5 CI/CD, ASSOC-S6 Troubleshooting (10% each)

- S5 missing: Git dialog operations and conflicts, notebook source formats,
  variable types and override precedence, `run_as`, what `mode: production`
  enforces, `bundle summary` / `destroy` / `generate`, auth precedence.
  Add a **promotion walkthrough** across three targets with resolved values and
  a **development vs production mode table**.
- S6 missing: run result states, the Jobs / Stages / Tasks hierarchy and Summary
  Metrics quartiles, `Exchange` nodes, `repartition` vs `coalesce`, `CLUSTER BY`
  syntax and limits (four keys, `OPTIMIZE FULL`), `VACUUM DRY RUN`, init script
  location rules, `%pip` vs cluster libraries, driver vs executor OOM messages.
  Add **reading one stage page** with three annotated fingerprints, a
  **partitioning vs Z-order vs clustering** comparison, and an **OOM triage
  tree**.

### ASSOC-S1 Platform (6%)

- Missing: control plane vs compute plane, classic vs serverless compute plane,
  metastore scope, `_delta_log` mechanics, `RESTORE`, `VACUUM` bounds on time
  travel, clones, generated columns, access modes, DBU, Photon, warehouse tiers.
- Add: **what a commit is** (one INSERT, UPDATE and RESTORE through `DESCRIBE
  HISTORY`), **time travel's expiry date**, **choosing compute in three
  questions**, **where the data sits**.

### PRO-S1 Developing Code (22%)

- The largest hole in the Professional bank is **Structured Streaming**: no note
  covers triggers, output modes, watermarks and late data, stateful operations,
  stream-stream joins, checkpoint contents and when a checkpoint must be reset,
  or `foreachBatch` idempotence with `txnVersion` / `txnAppId`. Also missing:
  bundle `artifacts` and `include`, `%pip` vs `%sh pip`, pandas UDF variants,
  Auto Loader options, `create_streaming_table` + `append_flow`, `STORED AS SCD
  TYPE 2` columns, `AUTO CDC FROM SNAPSHOT`, dynamic value references, retry
  knobs, `assertDataFrameEqual` tolerances.
- Add: a dedicated **Structured Streaming sub-note** (referenced from S1, S2, S6
  and S7): **exactly-once end to end**, **watermark arithmetic worked**, a
  **pipeline primitive chooser** (streaming table / MV / append_flow / AUTO CDC /
  foreachBatch), and **`run_if` scenarios**.

### PRO-S6 Optimization (13%)

- Missing: `delta.targetFileSize`, optimized writes and auto compaction,
  `delta.logRetentionDuration`, deletion vectors as a table feature, the
  32-column statistics default, dynamic file pruning, disk cache vs `CACHE`,
  AQE knobs, job vs all-purpose cost, CDF options and retention.
- Add: **anatomy of a slow query** (one profile read top to bottom), the
  **deletion vector lifecycle** (DELETE, PURGE, VACUUM), and **shuffle partitions
  and spill** at two data sizes.

### PRO-S3, PRO-S5, PRO-S7, PRO-S9 (10% each)

- S3 missing: join strategies and hints, salting, AQE skew join, `QUALIFY`,
  higher-order functions, `rollup` / `cube`, Python expectation decorators,
  event log expectation metrics. Add **which join will Spark pick** and
  **expectation semantics side by side**.
- S5 missing: `list_prices` to convert DBUs to money, `usage_metadata` columns,
  `system.query.history`, `event_log()` and the `flow_progress` JSON path, alert
  condition options, `notification_settings`. Add a **which table answers which
  question** matrix and **reading one `flow_progress` event**.
- S7 missing: compute policies (in O1), secret scopes and redaction, OAuth
  service principals, the deletion-vector erasure trap, CDF `_change_data`
  files, downstream copies. Add **erasure that actually erases** and **secrets
  end to end**.
- S9 missing: Spark UI failure signatures, log types and delivery, `rerun_tasks`
  vs `rerun_all_failed_tasks`, checkpoint incompatibility rules, `bundle
  generate` and `deployment bind`, `setup-cli` and env-var auth. Add **repair
  with a diagram** and **when to reset a checkpoint**.

### PRO-S2, PRO-S8, PRO-S10, PRO-S4 (5 to 7% each)

- S2: Kafka options, `from_avro`, reader `mode` and `badRecordsPath`,
  `skipChangeCommits`, `delta.appendOnly`. Add **append-only as a contract**.
- S8: lineage tables, governed tags, admin roles, workspace bindings. Add **can
  they read it, in five steps**.
- S10: identity columns, `RELY`, column mapping, SCD 1/2/3 definitions, fact
  types, additive measures, `CLUSTER BY AUTO` prerequisites. Add **SCD2 MERGE
  line by line** and **grain violations that pass tests**.
- S4: token rotation, `CURRENT_RECIPIENT()` in shared views, `PARTITION` on
  `ADD TABLE`, federation pushdown rules and `remote_query`. Add **D2D vs D2O
  walkthrough** and **what federation pushes down**.

## Cross-cutting

1. **"What the exam asks" box** at the top of every note: four to six one-line
   scenario stems mapped to the concept and objective id.
2. **"Defaults and limits" strip** per section: 10 MB broadcast, 200 shuffle
   partitions, 7-day VACUUM, 30-day log retention, 48 KiB task values, 4
   clustering keys, 32 statistics columns, 100 for-each concurrency.
3. **Every objective gets at least one command block** with the option names the
   exam uses and the default where one exists.
4. **Naming line** per note: Lakeflow Jobs (Workflows), Spark Declarative
   Pipelines (DLT, `@dlt` to `@dp`, `LIVE` gone), Connect, Declarative
   Automation Bundles, Git folders (Repos), Standard / Dedicated access modes.
   Old names still appear in distractors.
5. **Separate measured-on-Free-Edition facts** from general behaviour with one
   consistent callout, so a candidate does not memorise a workspace quirk.
6. **Notes should not restate the notebooks**; spend the words on what a
   notebook cannot show (theory-only objectives such as ASSOC-S1-O2 and
   ASSOC-S6-O5 are the thinnest today).

## Visuals: where to start

The renderer already reserves the `img` override for this: a note references
`![caption](visuals/name.svg)` or `visuals/name.html`, the build copies
`content/lessons/<exam>/S<n>/visuals/` into the app bundle, and the override
renders an `<img>` for SVG or a sandboxed `<iframe>` for HTML. One self-contained
HTML file per visual, no external assets, keeps the Databricks App CSP happy.

Start with interactive HTML where the concept is a **sequence or a state
machine**, because those are the ones prose explains worst and a static diagram
explains barely better. Ranked by exam weight, difficulty of the concept and
ease of building:

1. **Job DAG with `run_if`** (ASSOC-S4, PRO-S1-O9, PRO-S9). Click a task to fail
   it, pick a `run_if` value for the dependant, watch states resolve; a Repair
   button re-runs the right subset. One file serves three sections.
2. **Delta commit sequence** (ASSOC-S1, PRO-S6, PRO-S7). Files land, a JSON
   commit is appended, the reader pointer moves; then DELETE with a deletion
   vector, then VACUUM removing what history no longer references.
3. **Auto Loader checkpoint vs schema location** (ASSOC-S2, PRO-S2). Files
   arrive, the checkpoint ledger grows; delete the checkpoint and watch files
   re-ingest, delete the schema location and watch nothing reload.
4. **Privilege inheritance tree** (ASSOC-S7, PRO-S8). Grant at schema level and
   every current and future table lights up; revoke at table level and nothing
   changes; toggle a row filter for two principals.
5. **Watermark timeline** (PRO-S1). Events on a time axis, the watermark line
   advancing, windows closing, one late row falling outside.
6. **SCD2 half-open intervals** (PRO-S10). A customer changing segment, a fact
   date landing exactly on the boundary, exactly one match with `<` and two with
   `<=`.
7. **Join fan-out** (ASSOC-S3). A dimension with two versions of one key; watch
   the fact row duplicate, then the point-in-time predicate remove one.

Use **GIFs (screen recordings)** where the subject is the Databricks UI itself,
which cannot be drawn: the Spark UI stage page with skew and spill highlighted
(ASSOC-S6, PRO-S6), the Jobs matrix view and a repair run (ASSOC-S4, PRO-S9), a
query profile (PRO-S6), the Git folder dialog (ASSOC-S5), and the Catalog
Explorer permissions tab (ASSOC-S7). All of these can be recorded on Free
Edition; keep each under ten seconds and a few hundred kilobytes.

**Videos** are linked, not embedded, in the Further reading footers. Embedding
is possible later (a `youtube` fence rendered as a sandboxed iframe), but links
keep the notes self-contained and avoid a third-party frame inside the app.
