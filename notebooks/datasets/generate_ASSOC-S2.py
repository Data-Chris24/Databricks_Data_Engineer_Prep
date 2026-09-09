# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S2 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Run this once before working through Section 2. It writes two datasets to
# MAGIC `/Volumes/workspace/de_prep/raw/`:
# MAGIC
# MAGIC | | Used by | Shape |
# MAGIC |---|---|---|
# MAGIC | `s2_teach/` | the worked lessons | **flat** retail orders, CSV + JSON |
# MAGIC | `s2_assess/` | the graded assignment | **nested** sensor events, JSON only |
# MAGIC
# MAGIC The two are deliberately different in structure, not just in content. The
# MAGIC assignment cannot be completed by pasting the lesson's code, because the
# MAGIC assess data needs work the teach data never asks for: exploding an array,
# MAGIC converting epoch-millisecond timestamps, deduplicating a business key, and
# MAGIC surviving a schema change mid-stream.
# MAGIC
# MAGIC Everything is seeded, so every learner gets byte-identical data and the
# MAGIC graded answers are the same everywhere.

# COMMAND ----------

import json
import random
from datetime import datetime, timedelta, timezone

VOLUME = "/Volumes/workspace/de_prep/raw"
SEED = 20260904  # do not change - the assignment's expected answers depend on it

TEACH = f"{VOLUME}/s2_teach"
ASSESS = f"{VOLUME}/s2_assess"

dbutils.fs.mkdirs(TEACH)
dbutils.fs.mkdirs(ASSESS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## The `teach` dataset — flat retail orders
# MAGIC
# MAGIC One row per order. Two batches so `COPY INTO` and Auto Loader have something
# MAGIC incremental to do. Nulls in `discount_pct` give the lesson a cleaning step,
# MAGIC and `quantity` arrives as a string so there is a cast to talk about.

# COMMAND ----------

rng = random.Random(SEED)

PRODUCTS = ["ESP-100", "ESP-250", "GRD-010", "FLT-500", "MUG-021", "BNS-900"]
STORES = ["boston", "denver", "seattle", "austin"]
BASE = datetime(2026, 3, 1, tzinfo=timezone.utc)


def teach_rows(n, start_id, day_offset):
    rows = []
    for i in range(n):
        ordered = BASE + timedelta(days=day_offset, minutes=rng.randint(0, 1439))
        rows.append({
            "order_id": f"ORD-{start_id + i:06d}",
            "store": rng.choice(STORES),
            "product_sku": rng.choice(PRODUCTS),
            # deliberately a STRING - the lesson casts it
            "quantity": str(rng.randint(1, 6)),
            "unit_price": round(rng.uniform(4.5, 89.0), 2),
            # ~15% null - the lesson cleans it
            "discount_pct": None if rng.random() < 0.15 else round(rng.uniform(0, 0.35), 2),
            "ordered_at": ordered.isoformat(),
        })
    return rows


batch1 = teach_rows(500, 1, 0)
batch2 = teach_rows(300, 501, 1)

# CSV for the COPY INTO lesson
header = "order_id,store,product_sku,quantity,unit_price,discount_pct,ordered_at"


def to_csv(rows):
    out = [header]
    for r in rows:
        disc = "" if r["discount_pct"] is None else r["discount_pct"]
        out.append(
            f'{r["order_id"]},{r["store"]},{r["product_sku"]},{r["quantity"]},'
            f'{r["unit_price"]},{disc},{r["ordered_at"]}'
        )
    return "\n".join(out) + "\n"


dbutils.fs.put(f"{TEACH}/orders_2026-03-01.csv", to_csv(batch1), overwrite=True)
dbutils.fs.put(f"{TEACH}/orders_2026-03-02.csv", to_csv(batch2), overwrite=True)

print(f"teach: {len(batch1)} + {len(batch2)} order rows written to {TEACH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The `assess` dataset — nested sensor events
# MAGIC
# MAGIC Structurally different from `teach` in four ways, each of which defeats a
# MAGIC straight copy of the lesson code:
# MAGIC
# MAGIC 1. **Nested** — each file holds a device with an array of `readings`, so the
# MAGIC    rows the assignment wants only exist after an `explode`.
# MAGIC 2. **Epoch-millisecond timestamps** — integers, not ISO strings. Reading them
# MAGIC    as timestamps directly gives nonsense dates rather than an error, which is
# MAGIC    the interesting failure.
# MAGIC 3. **Duplicate `event_id`s** — the same reading is redelivered in a later
# MAGIC    file, so a correct answer deduplicates. The teach data has no duplicates.
# MAGIC 4. **A schema change mid-stream** — the third batch adds a `battery_pct`
# MAGIC    field. Auto Loader must be told to evolve, or the column is silently lost.

# COMMAND ----------

rng = random.Random(SEED + 1)

DEVICES = [f"sensor-{i:03d}" for i in range(1, 13)]
SITES = ["north-plant", "south-plant", "depot"]
EPOCH_BASE = int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)


def reading(event_id, minute_offset, with_battery):
    r = {
        "event_id": f"EVT-{event_id:07d}",
        # epoch MILLISECONDS, not an ISO string
        "recorded_at_ms": EPOCH_BASE + minute_offset * 60_000,
        "temperature_c": round(rng.uniform(-4.0, 41.0), 2),
        "humidity_pct": round(rng.uniform(10.0, 95.0), 1),
    }
    if with_battery:
        r["battery_pct"] = round(rng.uniform(20.0, 100.0), 1)
    return r


def device_docs(n_devices, first_event, minute_start, with_battery):
    docs, event_id = [], first_event
    for d in range(n_devices):
        n_readings = rng.randint(3, 7)
        readings = []
        for k in range(n_readings):
            readings.append(reading(event_id, minute_start + k * 5, with_battery))
            event_id += 1
        docs.append({
            "device_id": rng.choice(DEVICES),
            "site": rng.choice(SITES),
            "firmware": rng.choice(["1.4.2", "1.5.0", "2.0.1"]),
            "readings": readings,
        })
    return docs, event_id


def write_ndjson(path, docs):
    dbutils.fs.put(path, "\n".join(json.dumps(d) for d in docs) + "\n", overwrite=True)


# Batch 1 and 2: no battery field yet.
docs1, next_id = device_docs(10, 1, 0, with_battery=False)
write_ndjson(f"{ASSESS}/events_2026-03-01.json", docs1)

docs2, next_id = device_docs(10, next_id, 60, with_battery=False)
write_ndjson(f"{ASSESS}/events_2026-03-02.json", docs2)

# Batch 3: schema evolves - battery_pct appears. Also redelivers some of
# batch 2's readings verbatim, so event_id is no longer unique across files.
docs3, next_id = device_docs(8, next_id, 120, with_battery=True)
redelivered = [
    {**d, "readings": d["readings"][:2]}          # a partial replay of batch 2
    for d in docs2[:3]
]
write_ndjson(f"{ASSESS}/events_2026-03-03.json", docs3 + redelivered)

total_docs = len(docs1) + len(docs2) + len(docs3) + len(redelivered)
print(f"assess: {total_docs} device documents written to {ASSESS}")
print("  batch 3 adds battery_pct and replays some batch-2 readings")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What the assignment will ask for
# MAGIC
# MAGIC Deliberately not the same task as the lesson. See
# MAGIC `notebooks/assignments/ASSOC-S2/README.md` for the output contract.

# COMMAND ----------

for p in (TEACH, ASSESS):
    print(p)
    for f in dbutils.fs.ls(p):
        print(f"  {f.name:32} {f.size:>9,} bytes")
