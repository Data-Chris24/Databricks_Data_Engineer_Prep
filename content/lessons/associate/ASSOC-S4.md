# Working with Lakeflow Jobs — 16%

Orchestration: task graphs, triggers, and what happens when part of a job fails.

## Tasks and the DAG — `ASSOC-S4-O2`

A job is a graph of tasks with dependencies. A task runs when **all** of its
dependencies have succeeded.

**A job is not a transaction.** This is the most consequential idea in the section.
Given A → (B, C) → D, if C fails:

- A and B **completed**, and whatever they wrote to the lakehouse **stays written**
- C failed, and writes it committed before failing are still there
- D is **skipped**, not failed

Delta gives ACID guarantees per write operation, never across a job. Nothing rolls
back for you.

**Task types:** notebook, Python script, Python wheel, SQL (query, alert, dashboard
refresh), pipeline, dbt, JAR, and nested jobs. There is no "run a shell command" task —
that happens inside a notebook or script.

**Task values** pass small results between tasks and show up in the run history. They
also enable conditional branching, since a condition can test one.

## Control flow — `ASSOC-S4-O1`

**Retries assume idempotence.** A retry reruns the task from the start. If the failed
attempt already committed writes and the retry blindly appends the same data, you get
duplicates. Idempotent design — overwrite a partition, `MERGE` on a key, or a
checkpoint — is what makes retries safe. Retries are a design decision, not a checkbox.

**If/else conditions** branch on a value, usually a task value from an earlier task.
Keeping the branch in the job graph rather than inside a notebook means the run
history shows which path a run took.

**For each** runs one iteration per input value, with per-iteration visibility,
retries and controllable concurrency. Adding a new value becomes a data change rather
than a job change.

## Triggers — `ASSOC-S4-O3`, `ASSOC-S4-O4`

| Trigger | Fires | Use when |
|---|---|---|
| Scheduled (cron) | at fixed times | the cadence is genuinely time-based |
| File arrival | when files land | arrival time is unpredictable and latency matters |
| Table update | when a table changes | you depend on data, not on someone's schedule |
| Continuous | keeps running | genuinely never-ending work |

**Choose time-based or data-driven by what you actually depend on.** If a downstream
job cares that upstream *finished*, a table update trigger decouples the two — the
upstream schedule can change and the dependency still holds. A cron offset "shortly
after upstream usually finishes" is a coupling you have to re-tune forever.

A file arrival trigger beats polling: one prompt run when there is something to
process, instead of two dozen empty runs a night.

**Max concurrent runs is 1.** What happens to a trigger that fires while a run is
active depends on queueing: jobs created in the UI have it on by default and the new
run waits; with queueing off (the default for jobs created from the API or a bundle
unless `queue.enabled` is set) the run is skipped, and a job that consistently
overruns its schedule silently halves its frequency.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) — the top of the jobs documentation.
- [Configure and edit jobs](https://docs.databricks.com/aws/en/jobs/configure-job) — tasks, compute, parameters and notifications.
- [Control the flow of tasks](https://docs.databricks.com/aws/en/jobs/control-flow) — dependencies, conditions, branching and loops.
- [Run if conditions](https://docs.databricks.com/aws/en/jobs/run-if) — the six `run_if` values.
- [For each tasks](https://docs.databricks.com/aws/en/jobs/for-each) — looping over a list with a concurrency cap.
- [Task values](https://docs.databricks.com/aws/en/jobs/task-values) — passing results between tasks.
- [Trigger types](https://docs.databricks.com/aws/en/jobs/triggers) — schedule, continuous, file arrival and table update.
- [File arrival triggers](https://docs.databricks.com/aws/en/jobs/file-arrival-triggers) — the settings that stop a trigger firing on half-written data.
- [Repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures) — what a repair run re-executes.
- [Job and task parameters](https://docs.databricks.com/aws/en/jobs/parameters) — parameters, widgets and dynamic value references.

Videos for another angle on the hard parts (channel, length):

- [Databricks Lakeflow Jobs Tutorial: exploring the Jobs UI step by step](https://www.youtube.com/watch?v=xnuQ94qLsWc) — DataMindAI with Ahmed, 27 min. Every screen the exam describes in words, shown.
