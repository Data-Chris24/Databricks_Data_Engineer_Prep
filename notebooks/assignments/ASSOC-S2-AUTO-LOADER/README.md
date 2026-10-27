# Assignment — `ASSOC-S2-AUTO-LOADER` Five sources, five formats (optional)

**Objectives exercised:** `ASSOC-S2-O1`, `ASSOC-S2-O3`

**Optional.** It goes with the optional lesson `04_optional_auto_loader_deep_dive`
and does not count toward completing Section 2. Pass the section's own assignment
for that.

## Before you start

1. Work through `notebooks/lessons/associate/S2/04_optional_auto_loader_deep_dive`.
2. The data comes with the section's datasets. If
   `/Volumes/workspace/de_prep/raw/s2_al_assess/` is missing, run the lesson's first
   cell (it generates it) or `databricks bundle run generate_datasets_assoc_s2 -t free`.

> **The lesson's code will not solve this.** Every source is a format the lesson
> covered, exported differently. Copying the lesson's streams and changing the paths
> produces tables that fail the tests. Look at each source before you write a stream
> for it.

## The task

A ferry operator drops its exports in `/Volumes/workspace/de_prep/raw/s2_al_assess/`:

| Folder | Holds |
|---|---|
| `tickets/` | ticket sales, CSV |
| `vessels/batch_1/`, `vessels/batch_2/` | the fleet register, JSON, in two deliveries |
| `manifests/` | what each crossing carried, XML |
| `crossings/` | each crossing's departure and load, ORC |
| `scans/` | scanned boarding cards, among other files |

Load each one into its own table **with Auto Loader** (`cloudFiles`, trigger
`availableNow`). You are not told the files' layout: opening them is part of the job.

## The output contract

Five tables in `workspace.de_prep`. Every one must be written by an Auto Loader
stream: the tests read each table's history and expect `STREAMING UPDATE`, so a batch
`spark.read` and `saveAsTable` fails them even with the right rows.

Every stream keeps its state under `/Volumes/workspace/de_prep/raw/s2_al_work/<table>/`:
its checkpoint in `_checkpoint` and its schema location in `_schema`.

### `workspace.de_prep.ferry_tickets`

| Column | Type | Meaning |
|---|---|---|
| `ticket_no` | `STRING` | The ticket, unique per row |
| `route` | `STRING` | e.g. `DOV-CAL` |
| `vessel` | `STRING` | The vessel code |
| `departs` | `TIMESTAMP` | Scheduled departure. **Never null** |
| `fare_gbp` | `DECIMAL(8,2)` | The fare. Null where the export holds something that is not a price |
| `passengers` | `INT` | Passengers on the ticket |
| `remarks` | `STRING` | Desk remarks, possibly over several lines. **Null where there are none** |
| `_rescued_data` | `STRING` | What did not fit, kept by Auto Loader |

### `workspace.de_prep.ferry_vessels`

| Column | Type | Meaning |
|---|---|---|
| `vessel_code` | `STRING` | The vessel, unique per row |
| `name` | `STRING` | Its name |
| `built` | `BIGINT` | Year built |
| `decks` | `BIGINT` | Number of decks |
| `engine` | `STRUCT<kw: BIGINT, make: STRING>` | A struct you can query as `engine.make`, not a JSON string |
| `imo_number` | `STRING` | Only the second delivery has it. **Null for the vessels in the first** |

Column order is not checked for this table. Any other columns (such as
`_rescued_data`) may stay.

### `workspace.de_prep.ferry_manifests`

| Column | Type | Meaning |
|---|---|---|
| `crossing` | `STRING` | The crossing, unique per row |
| `route` | `STRING` | Its route |
| `cars` | `BIGINT` | Cars carried |
| `freight_units` | `BIGINT` | Freight units carried |
| `hazardous` | `BOOLEAN` | Whether it carried hazardous goods |
| `_rescued_data` | `STRING` | What did not fit |

Column order is not checked for this table.

### `workspace.de_prep.ferry_crossings`

| Column | Type | Meaning |
|---|---|---|
| `crossing` | `STRING` | The crossing, unique per row |
| `vessel` | `STRING` | Which vessel sailed it |
| `departed_at` | `TIMESTAMP` | When it left |
| `load_pct` | `DOUBLE` | How full it was |

### `workspace.de_prep.ferry_scans`

| Column | Type | Meaning |
|---|---|---|
| `path` | `STRING` | The scan's file |
| `modificationTime` | `TIMESTAMP` | When it was written |
| `length` | `BIGINT` | Its size in bytes |

### Requirements

1. **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
2. **The right folder for each location.** Each stream's checkpoint is
   `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
   The tests look inside both, so a swapped pair fails.
3. **Tickets parse completely.** One row per ticket, multi-line remarks intact,
   `departs` never null, `N/A` read as null, and the fares that are not prices left
   null in `fare_gbp` with their original text in `_rescued_data`.
4. **The vessels arrive in two deliveries, and so must your stream.** Land
   `batch_1` and run the stream; then land `batch_2` and run it again (the starter
   has a `land_vessels(n)` helper). The second run meets a field the first never
   saw. The table's history must show both loads, and `imo_number` must be filled for
   the second delivery only.
5. **Manifests: one row per crossing**, with the attribute names as the contract
   spells them.
6. **Scans: boarding-card images only, without their bytes.** The folder holds other
   files; none of them belongs in the table, and neither does a `content` column.
7. **Column order matters** for `ferry_tickets`, `ferry_crossings` and
   `ferry_scans`. The tests use `assertSchemaEqual`.

> **Clean-up removes only the resources listed on this unit's page in the study app**, the output tables above among them. A table you create under any other name is not removed by it: drop it yourself, or use **Remove** under *Not managed by the app*.

## How you are graded

**Unit tests — authoritative.** Run them with:

```bash
databricks bundle run grade_assoc_s2_auto_loader -t free --profile FREE
```

They check each table's schema and row count, that Auto Loader wrote it, both
locations of every stream, the parsed timestamps and the rescued fares, that the
vessels table evolved across two loads, and a few known values.

**AI review — advisory, optional.** If you have attached a model (see
`docs/grading.md`), it also reviews *how* you did it: whether each option sits on the
reader or the writer for the right reason. It can never overturn a unit test result.

## Hints, if you want them

<details>
<summary>I do not know where to start</summary>

`dbutils.fs.head(path, 600)` on one file per folder. For each, write down the
separator or row element, how a missing value is written, and how a timestamp is
written. Those notes are your reader options.
</details>

<details>
<summary>`departs` is null on every row</summary>

Inference did not recognise the date format, and a hint to `TIMESTAMP` cannot parse
it either: the original is in `_rescued_data`. There is a CSV reader option that
says how timestamps are written, in Spark's datetime pattern syntax.
</details>

<details>
<summary>The vessels stream failed with `UNKNOWN_FIELD_EXCEPTION`</summary>

That is the second run meeting the new field, working as designed. Run the cell
again. If the run after that fails with `DELTA_METADATA_MISMATCH`, one of the two
schema-evolution settings is missing; lesson 04 section 5 has the table.
</details>

<details>
<summary>The crossings stream fails before it starts</summary>

Read the error to the end: it names the option and the value it wants.
</details>

<details>
<summary>I need to start a table again</summary>

Drop the table **and** delete its folder under `s2_al_work/`. Dropping only the table
leaves the checkpoint, which remembers every file as done, so the next run loads
nothing.
</details>
