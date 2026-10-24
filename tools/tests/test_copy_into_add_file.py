"""The ASSOC-S2 COPY INTO lesson's add_orders_file() helper, run against a fake volume.

The helper's cell is pulled out of the notebook source and executed with a
dict-backed stand-in for dbutils.fs, so the 10-file cap, the file names and the
row contents are checked without a workspace.
"""

import csv
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

NOTEBOOK = (Path(__file__).resolve().parents[2]
            / "notebooks/lessons/associate/S2/01_copy_into.py")
LANDING = "/Volumes/workspace/de_prep/raw/s2_teach_copy_into"


class FakeFs:
    def __init__(self, names):
        self.files = {f"{LANDING}/{n}": "" for n in names}

    def ls(self, path):
        return [SimpleNamespace(name=p.rsplit("/", 1)[1], path=p)
                for p in sorted(self.files) if p.startswith(path + "/")]

    def put(self, path, contents, overwrite=False):
        if path in self.files and not overwrite:
            raise FileExistsError(path)
        self.files[path] = contents


def helper(fs):
    cells = NOTEBOOK.read_text().split("# COMMAND ----------")
    [cell] = [c for c in cells if "def add_orders_file" in c]
    ns = {"dbutils": SimpleNamespace(fs=fs), "LANDING": LANDING, "print": lambda *a: None}
    exec(cell, ns)
    return ns["add_orders_file"]


SEEDS = ["orders_2026-03-01.csv", "orders_2026-03-02.csv"]


def rows(contents):
    return list(csv.DictReader(io.StringIO(contents)))


def test_first_added_file_continues_from_the_seed_files():
    fs = FakeFs(SEEDS)
    path = helper(fs)()
    assert path == f"{LANDING}/orders_2026-03-03.csv"
    added = rows(fs.files[path])
    assert len(added) == 100
    assert added[0]["order_id"] == "ORD-000801"
    assert added[-1]["order_id"] == "ORD-000900"
    assert all(r["ordered_at"].startswith("2026-03-03") for r in added)
    assert list(added[0]) == ["order_id", "store", "product_sku", "quantity",
                              "unit_price", "discount_pct", "ordered_at"]


def test_files_stop_at_ten_with_a_reset_message():
    fs = FakeFs(SEEDS)
    add = helper(fs)
    paths = [add() for _ in range(8)]
    assert paths[-1].endswith("orders_2026-03-10.csv")
    ids = [r["order_id"] for p in paths for r in rows(fs.files[p])]
    assert len(ids) == len(set(ids)) == 800
    with pytest.raises(RuntimeError, match="maximum of 10 files.*reset the lesson"):
        add()
    assert len(fs.files) == 10


def test_every_learner_gets_the_same_file():
    a, b = FakeFs(SEEDS), FakeFs(SEEDS)
    pa, pb = helper(a)(), helper(b)()
    assert a.files[pa] == b.files[pb]
