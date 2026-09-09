<!-- GENERATED FILE - do not edit by hand.
     Source: content/objectives/associate.yaml
     Regenerate: python3 tools/render_objectives.py -->

# Databricks Certified Data Engineer Associate

Official exam guide version **2026-05-04**, retrieved 2026-09-09.
See [SOURCES.md](SOURCES.md) for the guide URL and the full exam facts.

**45 scored multiple-choice items · 90 minutes.**

## Section weightings

| # | Section | Weighting | Objectives |
| --- | --- | --- | --- |
| 1 | Databricks Intelligence Platform | 6% | 2 |
| 2 | Data Ingestion and Loading | 21% | 7 |
| 3 | Data Transformation and Modeling | 22% | 7 |
| 4 | Working with Lakeflow Jobs | 16% | 4 |
| 5 | Implementing CI/CD | 10% | 4 |
| 6 | Troubleshooting, Monitoring, and Optimization | 10% | 5 |
| 7 | Governance and Security | 15% | 4 |
| | **Total** | **100%** | **33** |

## Objectives

### Section 1: Databricks Intelligence Platform (6%)

- **`ASSOC-S1-O1`** — Understand the core components of the Databricks Data Intelligence Platform, such as its architecture, Delta Lake, and Unity Catalog.
- **`ASSOC-S1-O2`** — Understand Databricks Data Intelligence Platform's compute services, including their characteristics, limitations, and cost models, and select the most suitable option for each workload use case.
  - _Theory only on Free Edition · optional classic-compute lab_
  - Free Edition is serverless-only with no custom compute configuration, so comparing compute types and their cost models cannot be done hands-on here.

### Section 2: Data Ingestion and Loading (21%)

- **`ASSOC-S2-O1`** — Enable and detail data ingestion patterns, including batch, streaming, and incremental loading, and import data from sources such as local files, Lakeflow Connect standard connectors, and Lakeflow Connect managed connectors.
- **`ASSOC-S2-O2`** — Use the COPY INTO command to incrementally load files from cloud object storage (ADLS/S3/GCS) into Unity Catalog-governed tables.
- **`ASSOC-S2-O3`** — Use Auto Loader with schema enforcement and schema evolution in batch modes (for example, directory listing or file notification) to land data into Unity Catalog-governed tables.
- **`ASSOC-S2-O4`** — Configure Lakeflow Connect to reliably ingest data from diverse enterprise sources into Unity Catalog-governed tables.
  - _Partly hands-on on Free Edition_
  - Verified 2026-09-09. Standard connectors are fully hands-on - Auto Loader / read_files over a UC volume inside a declarative pipeline is the same product surface and needs no external system. Managed connectors are not creatable here: the database connectors require an ingestion gateway that runs on classic compute, which Free Edition does not have, and every dry-run pipeline spec carrying an ingestion_definition was rejected with "libraries must contain at least one element". Teach managed connectors as a spec walkthrough validated with a dry-run create, which consumes no quota.
- **`ASSOC-S2-O5`** — Use JDBC/ODBC or REST clients in notebooks to land data into cloud storage or directly into Unity Catalog-governed tables, usually orchestrated and scheduled with Lakeflow Jobs.
  - Verified 2026-09-09 on serverless (DBR 19.6, Spark 4.2) - better than expected, so no Lakebase project is needed. spark.read.format("jdbc") is fully supported and the bundled postgresql, mysql, sqlserver and databricks drivers all load. The lab reads from the workspace's OWN SQL warehouse over JDBC (jdbc:databricks://...;AuthMech=11; Auth_AccessToken=<token>;httpPath=/sql/1.0/warehouses/<id>) and writes into a UC table, which needs nothing external. Secret scopes also work here, so dbutils.secrets.get is available for the exam-shaped credential pattern. An external Postgres on 5432 was reachable too, but do not build the required path on that - it may depend on account-level verified internet access. An optional extension uses a Lakebase Postgres database as a real Postgres source, sharing the single Lakebase project with the study app. A local Docker Postgres cannot work here: serverless runs in Databricks' cloud and has no route to the learner's machine.
- **`ASSOC-S2-O6`** — Prioritize between Auto Loader, Lakeflow Connect (standard and managed connectors), partner connectors, and other ingestion methods based on technical requirements such as data volume, ingestion frequency, data types, and governance needs with Unity Catalog.
- **`ASSOC-S2-O7`** — Ingest semi-structured and unstructured data (for example, JSON and nested data) via Lakeflow Connect and other managed connectors into Unity Catalog-governed Delta tables.

### Section 3: Data Transformation and Modeling (22%)

- **`ASSOC-S3-O1`** — Implement data cleaning by reading bronze tables with PySpark/SQL, cleaning nulls, standardizing data types, and writing to new silver tables.
- **`ASSOC-S3-O2`** — Combine DataFrames with operations such as inner join, left join, broadcast join, multiple keys, cross join, union, and union all.
- **`ASSOC-S3-O3`** — Manipulate columns, rows, and table structures by adding, dropping, splitting, renaming column names, applying filters, and exploding arrays.
- **`ASSOC-S3-O4`** — Perform data deduplication operations and aggregate operations on DataFrames, such as count, approximate count distinct, mean, and summary.
- **`ASSOC-S3-O5`** — Understand the basic tuning parameters (spark.sql.shuffle.partitions, spark.default.parallelism, spark.executor/driver.memory, spark.sql.autoBroadcastJoinThreshold) and re-measure the performance.
- **`ASSOC-S3-O6`** — Understand the difference between, and how to build, Gold layer objects such as materialized views, views, streaming tables, and tables for BI and analytics teams in Unity Catalog.
- **`ASSOC-S3-O7`** — Apply data quality checks and validation rules to ensure reliable Silver and Gold datasets.

### Section 4: Working with Lakeflow Jobs (16%)

- **`ASSOC-S4-O1`** — Implement control flows (retries and conditional tasks such as branching and looping) using Lakeflow Jobs for pipeline orchestration.
- **`ASSOC-S4-O2`** — Configure common tasks (notebook, SQL query, dashboard, and pipeline tasks) and their dependencies using Lakeflow Jobs and its DAG-based task graph.
- **`ASSOC-S4-O3`** — Implement job schedules using Lakeflow Jobs with an understanding of trigger types (scheduled, file arrival, and table update).
- **`ASSOC-S4-O4`** — Choose between time-based and data-driven triggers based on data availability and pipeline dependencies.

### Section 5: Implementing CI/CD (10%)

- **`ASSOC-S5-O1`** — Manage your code development workflow within the Databricks workspace UI, including creating and switching between branches in Databricks Git Folders (formerly Databricks Repos), committing and pushing changes, and creating pull requests using Databricks Git integration.
- **`ASSOC-S5-O2`** — Understand environment-specific configuration using Automation Bundle (formerly Databricks Asset Bundles) variables and overrides while promoting the same codebase across dev, test, and prod targets.
- **`ASSOC-S5-O3`** — Deploy Declarative Automation Bundles (formerly Databricks Asset Bundles) to package, configure, and promote Lakeflow Jobs, Lakeflow Spark Declarative Pipelines, and other workspace assets across dev, test, and prod environments.
- **`ASSOC-S5-O4`** — Understand the Databricks CLI to validate, deploy, and manage Declarative Automation Bundles (formerly Databricks Asset Bundles) and other workspace assets in automated CI/CD workflows.

### Section 6: Troubleshooting, Monitoring, and Optimization (10%)

- **`ASSOC-S6-O1`** — Identify trends in job performance using the Lakeflow Jobs run history view to compare current execution times against historical baselines.
- **`ASSOC-S6-O2`** — Use the Lakeflow Jobs UI to monitor pipeline health by interpreting job statuses, viewing DAG-based task graphs to spot upstream blockers, and tracking pipeline run times and failure rates.
- **`ASSOC-S6-O3`** — Identify common performance bottlenecks such as data skew, shuffling, and disk spilling by interpreting stage-level metrics in the Spark UI.
  - _Partly hands-on on Free Edition · optional classic-compute lab · feasibility unverified_
  - Skew and spill can be induced on serverless, but Spark UI depth on serverless compute is limited. Confirm how much stage-level detail is actually visible; the classic lab covers the full diagnostic surface.
- **`ASSOC-S6-O4`** — Understand the features of Liquid Clustering and predictive optimization.
- **`ASSOC-S6-O5`** — Diagnose cluster startup failures, library conflicts, and out-of-memory issues.
  - _Theory only on Free Edition · optional classic-compute lab_
  - There are no clusters to fail to start on serverless. The classic lab deliberately breaks things - bad init script, conflicting pinned library versions, a forced driver OOM - so the real errors get read.

### Section 7: Governance and Security (15%)

- **`ASSOC-S7-O1`** — Differentiate between managed and external tables in Unity Catalog and perform basic operations (create, modify, delete, and convert between managed and external tables) on them.
- **`ASSOC-S7-O2`** — Configure access controls using the UI and SQL by applying GRANT, REVOKE, and DENY privileges to principals (users, groups, and service principals) at appropriate levels of the security hierarchy.
- **`ASSOC-S7-O3`** — Understand column-level masking and row-level security to restrict data visibility based on user groups.
- **`ASSOC-S7-O4`** — Understand Unity Catalog ABAC policies to centrally control row-level filtering and column masking for sensitive data.
  - _feasibility unverified_
  - ABAC policy availability on Free Edition is unconfirmed and the feature has been moving quickly. Check before writing a lab that depends on it.

## Recommended training (from the guide)

**Instructor-led**

- Data Engineering with Databricks

**Self-paced**

- Data Ingestion with Lakeflow Connect
- Deploy Workloads with Lakeflow Jobs
- DevOps Essentials for Data Engineering
- Data Interoperability with Unity Catalog
- Build Data Pipelines with Lakeflow Spark Declarative Pipelines
- Get Started with Data Governance on Databricks
