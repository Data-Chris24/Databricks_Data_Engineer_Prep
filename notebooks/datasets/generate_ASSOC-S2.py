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
# MAGIC | `s2_al_teach/` | the optional Auto Loader deep dive | one coffee-shop source per file format |
# MAGIC | `s2_al_assess/` | the optional Auto Loader assignment | five ferry-operator exports, five formats |
# MAGIC
# MAGIC The two are deliberately different in structure, not just in content. The
# MAGIC assignment cannot be completed by pasting the lesson's code, because the
# MAGIC assess data needs work the teach data never asks for: exploding an array,
# MAGIC converting epoch-millisecond timestamps, deduplicating a business key, and
# MAGIC surviving a schema change mid-stream.
# MAGIC
# MAGIC Everything is seeded, so every learner gets byte-identical data and the
# MAGIC graded answers are the same everywhere. The two `s2_al_*` folders were added
# MAGIC later with seeds of their own; adding them changed no byte of the first two.

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
# MAGIC ## The optional Auto Loader deep dive — one source per file format
# MAGIC
# MAGIC Two more folders, used only by the optional lesson
# MAGIC `04_optional_auto_loader_deep_dive` and the optional assignment
# MAGIC `ASSOC-S2-AUTO-LOADER`. Nothing above reads them, and they have their own
# MAGIC seeds, so adding them changed none of the bytes in `s2_teach` or `s2_assess`.
# MAGIC
# MAGIC | | `s2_al_teach/` (the lesson) | `s2_al_assess/` (the optional assignment) |
# MAGIC |---|---|---|
# MAGIC | Domain | the same coffee-shop retailer | a ferry operator |
# MAGIC | CSV | `;`-separated, quoted multi-line notes, a few bad prices | `|`-separated, `N/A` for null, `dd/MM/yyyy` times, bad fares |
# MAGIC | JSON | one pretty-printed array per file | the same, nested, and a second batch adds a field |
# MAGIC | Parquet · Avro · ORC | products · shipments · stock counts | ORC crossings |
# MAGIC | text · XML · binaryFile | till logs · suppliers · receipt images | manifests (XML) · ticket scans with stray files |
# MAGIC
# MAGIC Every file is written byte by byte from seeded values: Parquet and ORC through
# MAGIC `pyarrow` to a fixed file name, Avro by a small encoder below. Spark's own
# MAGIC writers would name each file `part-<uuid>` and stamp Avro with a random sync
# MAGIC marker, so two runs would differ.

# COMMAND ----------

import io
import struct
import zlib

AL_TEACH = f"{VOLUME}/s2_al_teach"
AL_ASSESS = f"{VOLUME}/s2_al_assess"


def put_bytes(path, data):
    """Write raw bytes to a volume path (dbutils.fs.put takes text only)."""
    dbutils.fs.mkdirs(path.rsplit("/", 1)[0])
    with open(path, "wb") as f:
        f.write(data)


def _zigzag(n):
    n = (n << 1) ^ (n >> 63)
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _avro_value(kind, v):
    if isinstance(kind, list):            # ["null", T]: branch index, then the value
        return _zigzag(0) if v is None else _zigzag(1) + _avro_value(kind[1], v)
    if kind == "string":
        b = v.encode("utf-8")
        return _zigzag(len(b)) + b
    if kind == "long" or kind == "int":
        return _zigzag(v)
    if kind == "double":
        return struct.pack("<d", v)
    raise ValueError(kind)


def avro_file(name, fields, rows, sync=b"de-prep-s2-avro!"):
    """An uncompressed Avro object container file: header, one data block."""
    schema = json.dumps({"type": "record", "name": name,
                         "fields": [{"name": n, "type": t} for n, t in fields]})
    meta = {"avro.schema": schema.encode(), "avro.codec": b"null"}
    head = b"Obj\x01" + _zigzag(len(meta))
    for k, v in meta.items():
        head += _avro_value("string", k) + _zigzag(len(v)) + v
    head += _zigzag(0) + sync
    body = b"".join(b"".join(_avro_value(t, r[n]) for n, t in fields) for r in rows)
    return head + _zigzag(len(rows)) + _zigzag(len(body)) + body + sync


def tiny_png(seed):
    """A valid 4x4 greyscale PNG whose pixels come from the seed."""
    r = random.Random(seed)
    raw = b"".join(b"\x00" + bytes(r.randrange(256) for _ in range(4)) for _ in range(4))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def arrow_bytes(table, writer):
    buf = io.BytesIO()
    writer(table, buf)
    return buf.getvalue()


def write_parquet(path, table):
    import pyarrow.parquet as pq
    put_bytes(path, arrow_bytes(table, lambda t, b: pq.write_table(t, b, compression="snappy")))


def write_orc(path, table):
    import pyarrow.orc as po
    put_bytes(path, arrow_bytes(table, lambda t, b: po.write_table(t, b)))


def csv_field(v, sep):
    """Quote a field when it holds the separator, a quote or a line break."""
    s = "" if v is None else str(v)
    if any(c in s for c in (sep, '"', "\n")):
        s = '"' + s.replace('"', '""') + '"'
    return s


def csv_text(header, rows, sep):
    lines = [sep.join(header)] + [sep.join(csv_field(r[h], sep) for h in header) for r in rows]
    return "\n".join(lines) + "\n"

# COMMAND ----------

# MAGIC %md
# MAGIC ### `s2_al_teach` — the lesson's sources

# COMMAND ----------

import pyarrow as pa
from datetime import date

rng = random.Random(SEED + 2)
dbutils.fs.rm(AL_TEACH, True)

NOTES = ["", "", "", "Happy birthday!", "Leave at the door", 'Ring twice; say "hi"',
         "Gift wrap please\nand no receipt", "Fragile:\nglass jar inside"]


def al_orders(n, start, day):
    rows = []
    for i in range(n):
        rows.append({
            "order_id": f"ORD-{start + i:06d}",
            "store": rng.choice(STORES),
            "product_sku": rng.choice(PRODUCTS),
            "quantity": rng.randint(1, 6),
            "unit_price": f"{rng.uniform(4.5, 89.0):.2f}",
            "gift_note": rng.choice(NOTES),
            "ordered_at": (BASE + timedelta(days=day, minutes=rng.randint(0, 1439))).isoformat(),
        })
    return rows


ORDER_COLS = ["order_id", "store", "product_sku", "quantity", "unit_price", "gift_note", "ordered_at"]
o1, o2 = al_orders(40, 700001, 0), al_orders(40, 700041, 1)
o1[7]["unit_price"] = "TBC"        # a price that is not a number: the rescue lesson
o2[12]["unit_price"] = "12,50"     # a decimal comma: the same lesson, another way
dbutils.fs.put(f"{AL_TEACH}/csv/orders_2026-03-01.csv", csv_text(ORDER_COLS, o1, ";"), overwrite=True)
dbutils.fs.put(f"{AL_TEACH}/csv/orders_2026-03-02.csv", csv_text(ORDER_COLS, o2, ";"), overwrite=True)

CITIES = [("boston", "02110"), ("denver", "80202"), ("seattle", "98101"), ("austin", "73301")]
customers = []
for i in range(1, 25):
    city, post = rng.choice(CITIES)
    customers.append({
        "customer_id": f"CUS-{i:04d}",
        "name": f"Customer {i:02d}",
        "address": {"city": city, "postcode": post},
        "tags": rng.sample(["wholesale", "newsletter", "barista", "subscriber"], rng.randint(0, 2)),
        "loyalty_points": rng.randint(0, 900),
    })
# One pretty-printed JSON array per file: what an API export usually looks like.
dbutils.fs.put(f"{AL_TEACH}/json/customers_part1.json", json.dumps(customers[:12], indent=2) + "\n", overwrite=True)
dbutils.fs.put(f"{AL_TEACH}/json/customers_part2.json", json.dumps(customers[12:], indent=2) + "\n", overwrite=True)

CATEGORY = {"ESP": "espresso machine", "GRD": "grinder", "FLT": "filter", "MUG": "mug", "BNS": "beans"}
write_parquet(f"{AL_TEACH}/parquet/products.parquet", pa.table({
    "sku": PRODUCTS,
    "category": [CATEGORY[p[:3]] for p in PRODUCTS],
    "list_price": [round(rng.uniform(6.0, 650.0), 2) for _ in PRODUCTS],
    "launched": [date(2024, rng.randint(1, 12), rng.randint(1, 28)) for _ in PRODUCTS],
}))

ship_fields = [("shipment_id", "string"), ("order_id", "string"), ("carrier", "string"),
               ("shipped_at_ms", "long"), ("weight_kg", ["null", "double"])]
shipments = [{
    "shipment_id": f"SHP-{i:05d}",
    "order_id": f"ORD-{700000 + rng.randint(1, 80):06d}",
    "carrier": rng.choice(["ups", "fedex", "usps"]),
    "shipped_at_ms": int((BASE + timedelta(days=1, minutes=rng.randint(0, 2000))).timestamp() * 1000),
    "weight_kg": None if rng.random() < 0.1 else round(rng.uniform(0.2, 9.0), 2),
} for i in range(1, 31)]
put_bytes(f"{AL_TEACH}/avro/shipments.avro", avro_file("shipment", ship_fields, shipments))

write_orc(f"{AL_TEACH}/orc/stock_counts.orc", pa.table({
    "store": [s for s in STORES for _ in PRODUCTS],
    "sku": [p for _ in STORES for p in PRODUCTS],
    "on_hand": [rng.randint(0, 120) for _ in STORES for _ in PRODUCTS],
    "counted_on": [date(2026, 3, 2)] * (len(STORES) * len(PRODUCTS)),
}))

LEVELS = ["INFO", "INFO", "INFO", "WARN", "ERROR"]
for day in (1, 2):
    lines = []
    t = datetime(2026, 3, day, 7, 0, tzinfo=timezone.utc)
    for _ in range(25):
        t += timedelta(seconds=rng.randint(20, 900))
        lines.append(f"{t.isoformat()} {rng.choice(LEVELS)} till-{rng.randint(1, 4)} "
                     f"{rng.choice(['opened', 'sale', 'refund', 'drawer open', 'printer jam'])}")
    dbutils.fs.put(f"{AL_TEACH}/text/till_2026-03-0{day}.log", "\n".join(lines) + "\n", overwrite=True)

sup = ['<?xml version="1.0" encoding="UTF-8"?>', "<suppliers>"]
for i, (name, country) in enumerate([("Roast Co", "DE"), ("Bean Bros", "CO"), ("Kiln Ware", "PT"),
                                     ("Grindworks", "IT"), ("Paper Filters Ltd", "GB")], start=1):
    sup.append(f'  <supplier id="SUP-{i:02d}" country="{country}">')
    sup.append(f"    <name>{name}</name>")
    sup.append(f"    <lead_time_days>{rng.randint(2, 21)}</lead_time_days>")
    sup.append("  </supplier>")
sup.append("</suppliers>")
dbutils.fs.put(f"{AL_TEACH}/xml/suppliers.xml", "\n".join(sup) + "\n", overwrite=True)

for i in range(1, 7):
    put_bytes(f"{AL_TEACH}/binary/receipts/receipt_{i:03d}.png", tiny_png(SEED + 100 + i))
dbutils.fs.put(f"{AL_TEACH}/binary/receipts/README.txt", "Scanned till receipts, one PNG each.\n", overwrite=True)

print("s2_al_teach written")

# COMMAND ----------

# MAGIC %md
# MAGIC ### `s2_al_assess` — the optional assignment's sources
# MAGIC
# MAGIC Not described here: discovering each source's shape is part of the task.

# COMMAND ----------

rng = random.Random(SEED + 3)
dbutils.fs.rm(AL_ASSESS, True)

ROUTES = ["DOV-CAL", "HOL-DUB", "POR-SAN", "ABD-KWL"]
VESSELS = [f"V{i:02d}" for i in range(1, 9)]
FERRY_BASE = datetime(2026, 4, 1, 6, 0)
REMARKS = [None, None, None, "wheelchair space", "pet in car", "late check-in,\nflagged by desk", 'group "Blue"']


def tickets(n, start, day):
    rows = []
    for i in range(n):
        dep = FERRY_BASE + timedelta(days=day, minutes=15 * rng.randint(0, 60))
        rows.append({
            "ticket_no": f"T{start + i:07d}",
            "route": rng.choice(ROUTES),
            "vessel": rng.choice(VESSELS),
            # dd/MM/yyyy HH:mm, so a timestamp needs a format option to parse
            "departs": dep.strftime("%d/%m/%Y %H:%M"),
            "fare_gbp": f"{rng.uniform(18, 240):.2f}",
            "passengers": rng.randint(1, 6),
            # the export writes N/A for a missing value, never an empty field
            "remarks": rng.choice(REMARKS) or "N/A",
        })
    return rows


TICKET_COLS = ["ticket_no", "route", "vessel", "departs", "fare_gbp", "passengers", "remarks"]
t1, t2 = tickets(60, 1, 0), tickets(60, 61, 1)
for rows, bad in ((t1, {5: "FREE", 33: "?"}), (t2, {17: "comp"})):
    for k, v in bad.items():
        rows[k]["fare_gbp"] = v


dbutils.fs.put(f"{AL_ASSESS}/tickets/tickets_2026-04-01.csv", csv_text(TICKET_COLS, t1, "|"), overwrite=True)
dbutils.fs.put(f"{AL_ASSESS}/tickets/tickets_2026-04-02.csv", csv_text(TICKET_COLS, t2, "|"), overwrite=True)


def vessel(code, with_imo):
    v = {
        "vessel_code": code,
        "name": f"MV {rng.choice(['Spirit', 'Pride', 'Star', 'Isle', 'Wave'])} of {rng.choice(['Kent', 'Erin', 'Bilbao', 'Orkney'])}",
        "built": rng.randint(1996, 2024),
        "engine": {"make": rng.choice(["Wartsila", "MAN", "MaK"]), "kw": rng.randint(8000, 32000)},
        "decks": rng.randint(5, 11),
    }
    if with_imo:
        v["imo_number"] = f"IMO{rng.randint(9000000, 9999999)}"
    return v


dbutils.fs.put(f"{AL_ASSESS}/vessels/batch_1/vessels_2026-04-01.json",
               json.dumps([vessel(c, False) for c in VESSELS[:5]], indent=2) + "\n", overwrite=True)
# The second batch adds a field the first never had.
dbutils.fs.put(f"{AL_ASSESS}/vessels/batch_2/vessels_2026-04-02.json",
               json.dumps([vessel(c, True) for c in VESSELS[5:]], indent=2) + "\n", overwrite=True)

man = ['<?xml version="1.0" encoding="UTF-8"?>', "<export>", "  <generated>2026-04-03</generated>", "  <manifests>"]
for i in range(1, 19):
    man.append(f'    <manifest crossing="X{i:04d}" route="{rng.choice(ROUTES)}">')
    man.append(f"      <cars>{rng.randint(0, 180)}</cars>")
    man.append(f"      <freight_units>{rng.randint(0, 60)}</freight_units>")
    man.append(f"      <hazardous>{str(rng.random() < 0.15).lower()}</hazardous>")
    man.append("    </manifest>")
man += ["  </manifests>", "</export>"]
dbutils.fs.put(f"{AL_ASSESS}/manifests/manifests_2026-04.xml", "\n".join(man) + "\n", overwrite=True)

write_orc(f"{AL_ASSESS}/crossings/crossings_2026-04.orc", pa.table({
    "crossing": [f"X{i:04d}" for i in range(1, 19)],
    "vessel": [rng.choice(VESSELS) for _ in range(18)],
    "departed_at": [FERRY_BASE + timedelta(hours=3 * i) for i in range(18)],
    "load_pct": [round(rng.uniform(12.0, 99.5), 1) for _ in range(18)],
}))

for i in range(1, 13):
    body = bytes(rng.randrange(256) for _ in range(rng.randint(40, 120)))
    put_bytes(f"{AL_ASSESS}/scans/2026-04/scan_{i:03d}.jpg", b"\xff\xd8\xff\xe0" + body + b"\xff\xd9")
dbutils.fs.put(f"{AL_ASSESS}/scans/2026-04/index.json", json.dumps({"scans": 12}) + "\n", overwrite=True)
dbutils.fs.put(f"{AL_ASSESS}/scans/2026-04/notes.txt", "rescanned 004 and 009\n", overwrite=True)

print("s2_al_assess written")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What the assignment will ask for
# MAGIC
# MAGIC Deliberately not the same task as the lesson. See
# MAGIC `notebooks/assignments/ASSOC-S2/README.md` for the output contract.

# COMMAND ----------

def tree(root):
    for f in dbutils.fs.ls(root):
        if f.isDir():
            yield from tree(f.path)
        else:
            yield f


for p in (TEACH, ASSESS, AL_TEACH, AL_ASSESS):
    print(p)
    for f in tree(p):
        print(f"  {f.path.split(p)[-1].lstrip('/'):44} {f.size:>9,} bytes")
