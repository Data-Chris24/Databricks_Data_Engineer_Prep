# Assignment — `PRO-S2` Data Ingestion & Acquisition

**Objectives:** `PRO-S2-O1`, `PRO-S2-O2`

## Before you start

Work both lessons in `notebooks/lessons/professional/S2/`, and generate the data
(`databricks bundle run generate_datasets_pro_s2 -t free`).

> **In the lesson, the sources agreed with each other.** Three formats, same column
> order, same types, each record delivered once — so `union` and `unionByName` gave
> the same answer and a plain append was correct. None of that holds here.

## The task

Five drop zones under `/Volumes/workspace/de_prep/raw/pro_s2/assess/`:

| Path | Format |
|---|---|
| `assess/json` | JSON |
| `assess/parquet` | Parquet |
| `assess/avro` | Avro |
| `assess/csv` | CSV, with a header |
| `assess/xml` | XML |

Between them they deliver 660 records covering 600 distinct scans. Land all of it in
an append-only bronze table, then produce a silver table with one row per scan.

**The schemas are not documented here on purpose.** Reading them off the sources is
part of the task, and the sources do not agree — on column order, on types, or on
how many times they send a record.

## The output contract

Both tables share this schema, in this order:

| Column | Type | Meaning |
|---|---|---|
| `scan_id` | `STRING` | business key |
| `facility` | `STRING` | one of LEEDS, DUBLIN, PORTO, MALMO, LYON |
| `carrier` | `STRING` | one of northwind, brightline, kestrel |
| `status` | `STRING` | received, in_transit, out_for_delivery, delivered |
| `weight_kg` | `DOUBLE` | |
| `scanned_at` | `TIMESTAMP` | |
| `revision` | `INT` | 1 for an original, higher for a correction |
| `route_code` | `STRING` | only one source sends it; `NULL` elsewhere |
| `source_format` | `STRING` | which drop zone this record came from |

**`workspace.de_prep.pro_s2_scans_bronze`** — append-only. Every delivered record,
corrections *and* the originals they supersede.

**`workspace.de_prep.pro_s2_scans`** — one row per `scan_id`: the highest `revision`
delivered for that scan.

### Requirements

1. **Every source lands.** If a format is missing from `source_format`, its reader
   needed an option you did not pass.
2. **Columns go where their names say.** Two sources ship the same columns in a
   different order, and the values are all strings, so nothing will error.
3. **No value is lost to parsing.** No null `scanned_at`, no null `weight_kg`.
4. **Bronze keeps the duplicates. Silver resolves them.** Those are different jobs;
   don't do the second one in the first table.
5. **Pin your types.** A union keeps the widest type it is given, so one source
   inferring `revision` as a `BIGINT` is enough to change the table's schema. State
   the types you want rather than accepting what the union settled on.
6. Column order matters — the tests compare the whole schema.

## Grading

```bash
databricks bundle run grade_pro_s2 -t free
```

The tests are authoritative. The advisory AI review (`grading/rubrics/PRO-S2.yaml`)
judges whether you read each format on its own terms or forced them all through one
reader, and whether bronze is genuinely append-only.
