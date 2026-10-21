<!-- GENERATED FILE - do not edit by hand.
     Source: content/objectives/professional.yaml
     Regenerate: python3 tools/render_objectives.py -->

# Databricks Certified Data Engineer Professional

Official exam guide version **2026-07-03**, retrieved 2026-09-09.
See [SOURCES.md](SOURCES.md) for the guide URL and the full exam facts.

**59 scored multiple-choice items · 120 minutes.**

> **On the weightings below:** this exam's guide PDF lists its sections *without* percentages. These come from the Databricks certification web page, so treat them as indicative rather than quoted.

## Section weightings

| # | Section | Weighting | Objectives |
| --- | --- | --- | --- |
| 1 | Developing Code for Data Processing using Python and SQL | 22% | 11 |
| 2 | Data Ingestion & Acquisition | 7% | 2 |
| 3 | Data Transformation, Cleansing, and Quality | 10% | 2 |
| 4 | Data Sharing and Federation | 5% | 3 |
| 5 | Monitoring and Alerting | 10% | 6 |
| 6 | Cost & Performance Optimization | 13% | 5 |
| 7 | Ensuring Data Security and Compliance | 10% | 5 |
| 8 | Data Governance | 7% | 2 |
| 9 | Debugging and Deploying | 10% | 5 |
| 10 | Data Modeling | 6% | 4 |
| | **Total** | **100%** | **45** |

## Objectives

### Section 1: Developing Code for Data Processing using Python and SQL (22%)

Guide groups these objectives under:
- Using Python and Tools for development
- Building and Testing an ETL pipeline with Lakeflow Spark Declarative Pipelines, SQL, and Apache Spark on the Databricks Platform

- **`PRO-S1-O1`** — Design and implement a scalable Python project structure optimized for Declarative Automation Bundles (formerly Databricks Asset Bundles / DABs), enabling modular development, deployment automation, and CI/CD integration.
- **`PRO-S1-O2`** — Manage and troubleshoot external third-party library installations and dependencies in Databricks, including PyPI packages, local wheels, and source archives.
  - _Partly hands-on on Free Edition · optional classic-compute lab_
  - Notebook-scoped %pip and serverless environments cover most of this. Cluster-scoped libraries and init scripts - and the conflicts they cause - need classic compute.
- **`PRO-S1-O3`** — Develop User-Defined Functions (UDFs) using Pandas/Python UDF.
- **`PRO-S1-O4`** — Build and manage reliable, production-ready data pipelines for batch and streaming data using Lakeflow Spark Declarative Pipelines and Auto Loader.
- **`PRO-S1-O5`** — Create and automate ETL workloads using Jobs via UI/APIs/CLI.
- **`PRO-S1-O6`** — Explain the advantages and disadvantages of streaming tables compared to materialized views.
- **`PRO-S1-O7`** — Use AUTO CDC APIs (formerly APPLY CHANGES) to simplify CDC in Lakeflow Spark Declarative Pipelines.
- **`PRO-S1-O8`** — Compare Spark Structured Streaming and Lakeflow Spark Declarative Pipelines to determine the optimal approach for building scalable ETL pipelines.
- **`PRO-S1-O9`** — Create a pipeline component that uses control flow operators (e.g., if/else, for/each, etc.).
- **`PRO-S1-O10`** — Choose the appropriate configs for environments and dependencies, high memory for notebook tasks, and auto-optimization to disallow retries.
  - _Partly hands-on on Free Edition · optional classic-compute lab_
  - Retry and environment config is doable on serverless; selecting high-memory compute for a notebook task is not.
- **`PRO-S1-O11`** — Develop unit and integration tests using assertDataFrameEqual, assertSchemaEqual, DataFrame.transform, and testing frameworks, to ensure code correctness, including a built-in debugger.

### Section 2: Data Ingestion & Acquisition (7%)

- **`PRO-S2-O1`** — Design and implement data ingestion pipelines to efficiently ingest a variety of data formats including Delta Lake, Parquet, ORC, AVRO, JSON, CSV, XML, Text and Binary from diverse sources such as message buses and cloud storage.
- **`PRO-S2-O2`** — Create an append-only data pipeline capable of handling both batch and streaming data using Delta.

### Section 3: Data Transformation, Cleansing, and Quality (10%)

- **`PRO-S3-O1`** — Write efficient Spark SQL and PySpark code to apply advanced data transformations, including window functions, joins, and aggregations, to manipulate and analyze large datasets.
- **`PRO-S3-O2`** — Develop a quarantining process for bad data with Lakeflow Spark Declarative Pipelines, or Auto Loader in classic jobs.

### Section 4: Data Sharing and Federation (5%)

- **`PRO-S4-O1`** — Demonstrate Delta Sharing securely between Databricks deployments using Databricks-to-Databricks sharing (D2D) or to external platforms using the open sharing protocol (D2O).
  - _Partly hands-on on Free Edition_
  - Settled by measurement 2026-09-09. The whole provider side is hands-on: CREATE SHARE, ALTER SHARE ADD TABLE/VOLUME with aliases and history options, CREATE RECIPIENT (DATABRICKS auth), GRANT SELECT ON SHARE, SHOW ALL IN SHARE and SHOW GRANTS ON SHARE. Open-protocol (TOKEN) recipients are refused - "External Delta Sharing is not enabled on the metastore", delta_sharing_scope is INTERNAL. The consumer side needs a second metastore: sharing to your own produces no provider, so CREATE CATALOG ... USING SHARE cannot be run.
- **`PRO-S4-O2`** — Configure Lakehouse Federation with proper governance across the supported source systems.
  - _Partly hands-on on Free Edition_
  - Settled by measurement 2026-09-09, for the two targets reachable here. All the DDL and governance is hands-on: CREATE CONNECTION, CREATE FOREIGN CATALOG, GRANT USE CONNECTION, grants on the foreign catalog, system.information_schema.connections, and the dependency rule that blocks dropping a connection a foreign catalog uses. None of it validates anything - a connection to a nonexistent host is accepted. The query path fails with FAILED_JDBC.CONNECTION, including for a databricks-type connection pointed at this workspace's own SQL warehouse. A Lakebase Postgres target is untested: the account gets one Lakebase project and it is reserved for the study app.
- **`PRO-S4-O3`** — Use Delta Sharing to share live data from the Lakehouse to any computing platform.
  - _Theory only on Free Edition_
  - Settled by measurement 2026-09-09. "Any computing platform" means the open sharing protocol, which needs a TOKEN recipient and a credential file. This metastore refuses to create one - delta_sharing_scope is INTERNAL, and enabling external sharing is a metastore-admin setting not available on Free Edition. Covered as theory, with the measured refusal shown in the lesson.

### Section 5: Monitoring and Alerting (10%)

Guide groups these objectives under:
- Monitoring
- Alerting

- **`PRO-S5-O1`** — Use system tables for observability over resource utilization, cost, auditing and workload monitoring.
  - Settled by measurement 2026-09-09. Thirteen system schemas are present and readable: access, ai, ai_gateway, alert, billing, compute, information_schema, lakeflow, mlflow, query, serving, storage, tags. system.billing.usage and system.access.audit both return rows, so cost and audit observability are fully hands-on.
- **`PRO-S5-O2`** — Use Query Profiler UI and Spark UI to monitor workloads.
  - _Partly hands-on on Free Edition · optional classic-compute lab_
  - Query Profiler works on the SQL warehouse. Spark UI depth is the gap - see ASSOC-S6-O3.
- **`PRO-S5-O3`** — Use the Databricks REST APIs / Databricks CLI for monitoring jobs and pipelines.
- **`PRO-S5-O4`** — Use Lakeflow Spark Declarative Pipelines event logs to monitor pipelines.
- **`PRO-S5-O5`** — Use SQL Alerts to monitor data quality.
- **`PRO-S5-O6`** — Use the Lakeflow Jobs UI and Jobs API to set up notifications for job status and performance issues.

### Section 6: Cost & Performance Optimization (13%)

- **`PRO-S6-O1`** — Understand how and why using Unity Catalog managed tables reduces operational overhead and maintenance burden.
- **`PRO-S6-O2`** — Understand Delta optimization techniques, such as deletion vectors and liquid clustering.
- **`PRO-S6-O3`** — Understand the optimization techniques used by Databricks to ensure the performance of queries on large datasets (data skipping, file pruning, etc.).
- **`PRO-S6-O4`** — Apply Change Data Feed (CDF) to address specific limitations of streaming tables and enhance latency.
- **`PRO-S6-O5`** — Use the query profile to analyze the query and identify bottlenecks, such as bad data skipping, inefficient types of joins, and data shuffling.

### Section 7: Ensuring Data Security and Compliance (10%)

Guide groups these objectives under:
- Applying Data Security mechanisms
- Ensuring Compliance

- **`PRO-S7-O1`** — Use ACLs to secure workspace objects, enforcing the principle of least privilege, including enforcing principles like least privilege and policy enforcement.
- **`PRO-S7-O2`** — Use row filters and column masks to filter and mask sensitive table data.
- **`PRO-S7-O3`** — Apply anonymization and pseudonymization methods, such as hashing, tokenization, suppression, and generalization, to confidential data.
- **`PRO-S7-O4`** — Implement a compliant batch and streaming pipeline that detects and applies masking of PII to ensure data privacy.
- **`PRO-S7-O5`** — Develop a data purging solution ensuring compliance with data retention policies.

### Section 8: Data Governance (7%)

- **`PRO-S8-O1`** — Create and add descriptions/metadata about enterprise data to make it more discoverable.
- **`PRO-S8-O2`** — Demonstrate understanding of the Unity Catalog permission inheritance model.

### Section 9: Debugging and Deploying (10%)

Guide groups these objectives under:
- Debugging and Troubleshooting
- Deploying CI/CD

- **`PRO-S9-O1`** — Identify pertinent diagnostic information using Spark UI, cluster logs, system tables, and query profiles to troubleshoot errors.
  - _Partly hands-on on Free Edition · optional classic-compute lab_
  - Query profiles are available; cluster log delivery is not, since there are no clusters. The classic lab covers root-causing a failure from delivered cluster logs.
- **`PRO-S9-O2`** — Analyze the errors and remediate the failed job runs with job repairs and parameter overrides.
- **`PRO-S9-O3`** — Use Lakeflow Spark Declarative Pipelines event logs and the Spark UI to debug Lakeflow Spark Declarative Pipelines and Spark pipelines.
- **`PRO-S9-O4`** — Build and deploy Databricks resources using Declarative Automation Bundles (formerly Databricks Asset Bundles).
- **`PRO-S9-O5`** — Configure and integrate with Git-based CI/CD workflows and Databricks Git folders (formerly Repos) for notebook and code deployment.

### Section 10: Data Modeling (6%)

- **`PRO-S10-O1`** — Design and implement scalable data models using Delta Lake to manage large datasets.
- **`PRO-S10-O2`** — Simplify data layout decisions and optimize query performance using Liquid Clustering.
- **`PRO-S10-O3`** — Identify the benefits of using Liquid Clustering over partitioning and ZORDER.
- **`PRO-S10-O4`** — Design dimensional models for analytical workloads, ensuring efficient querying and aggregation.

## Recommended training (from the guide)

**Instructor-led**

- Advanced Data Engineering with Databricks

**Self-paced**

- Advanced Techniques with Spark Declarative Pipelines
- Databricks Data Privacy
- Databricks Performance Optimization
- Automated Deployment with Declarative Automation Bundles
