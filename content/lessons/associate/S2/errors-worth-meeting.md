# Errors worth meeting on purpose

**Objectives:** `ASSOC-S2-O2`, `ASSOC-S2-O3`

Every error below was hit while building the Section 2 lessons — none are
hypothetical. Each is a case where Databricks fails *deliberately* to stop you
doing something worse silently, and each is the kind of thing the exam asks about
sideways: not "what does this error say" but "what will happen when…".

The habit worth building: **read the error, it usually tells you the fix.** Two of
these say it outright.

---

## 1. `DELTA_FAILED_TO_MERGE_FIELDS`

**When:** `COPY INTO` a table whose columns you declared as `DOUBLE`/`INT`, from CSV.

```
[DELTA_FAILED_TO_MERGE_FIELDS] Failed to merge fields 'unit_price' and 'unit_price'
```

**Why:** CSV has no types — every field is text until something interprets it.
`COPY INTO` will not silently coerce that text into your declared types, because
coercion is where data quietly goes wrong: `"12.5x"` becoming `12.5`, or a European
decimal comma becoming a different number entirely.

**The fix, and the better design:** make bronze all `STRING`, faithful to the
source, and cast on the way to silver. A value that will not cast becomes a null
you can *count* rather than a load that fails at 3am.

```sql
-- silver
SELECT CAST(quantity AS INT) AS quantity, ...
```

**Exam-shaped question:** you declare a typed table and `COPY INTO` a CSV — does it
cast, fail, or load nulls? It fails.

---

## 2. `UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE`

**When:** Auto Loader with `schemaEvolutionMode = addNewColumns` meets a column it
has not seen.

```
[UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE] Encountered unknown fields during
parsing: [channel], which can be fixed by an automatic retry: true
```

**Why this is not a bug:** read the last clause. Auto Loader records the wider
schema, then stops **so a human finds out the source changed**. A pipeline that
silently absorbs new columns is a pipeline nobody notices has changed.

**The fix:** run it again. Something must do the running:

- **interactively** — re-run the cell; you are the retry
- **in a job** — set `max_retries`, and the failure becomes invisible

**What does not work:** catching the exception inside one notebook run. See #4.

**Exam-shaped question:** a nightly Auto Loader job starts failing after upstream
adds a column, with retries disabled. What is happening, and what is the fix?

---

## 3. `DELTA_METADATA_MISMATCH`

**When:** the reader evolved but the writer did not.

```
[DELTA_METADATA_MISMATCH] A schema mismatch detected when writing to the Delta
table. To enable schema migration ... set: .option("mergeSchema", "true")
```

**Why:** schema evolution takes **two** settings, one on each side, and only one of
them is named like it.

| Setting | Side | Without it |
|---|---|---|
| `cloudFiles.schemaEvolutionMode` | reader | Auto Loader never notices the column |
| `mergeSchema` | writer | the Delta table rejects it — this error |

Setting only the first is the most common version of this mistake, because it is
the one that *sounds* like "the schema evolution option".

**Exam-shaped question:** `schemaEvolutionMode` is set to `addNewColumns` and the
job still fails on a new column. What is missing?

---

## 4. `Some streams terminated before this command could finish!`

**When:** a streaming query fails inside a notebook — **even if you caught the
exception**.

**Why:** Databricks tracks terminated streaming queries per notebook, separately
from Python exception handling. The cell fails on that bookkeeping regardless of
your `try`/`except`, and `spark.streams.resetTerminated()` does not clear it.

**The fix:** stop trying to handle a stream failure inside the notebook run. Let the
restart come from outside it — you re-running the cell, or a job retry policy.

This is worth knowing because the instinct to wrap it in `try`/`except` is a good
instinct that happens to be wrong here, and the error message gives no hint as to
why.

---

## The pattern underneath all four

Databricks fails loudly where the alternative is failing quietly:

| It refuses to | Because silently doing it would |
|---|---|
| Coerce CSV text into declared types | change your numbers |
| Absorb a new column without stopping | hide a source change |
| Widen a Delta table implicitly | let a typo become a column |
| Pretend a dead stream is fine | lose data you believed was loaded |

When something fails on Databricks, the useful first question is usually *what
would have gone wrong if this had worked?*
