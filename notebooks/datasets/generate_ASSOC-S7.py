# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S7 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Governance is about *who sees what*, so the datasets differ in **what needs
# MAGIC protecting** rather than in shape.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **Teach has one sensitive column. Assess has several, of different kinds** —
# MAGIC    an identifier to hash, a free-text note that may contain anything, and a
# MAGIC    salary that some roles may aggregate but never read per-row.
# MAGIC 2. **Teach has one audience. Assess has three**, with overlapping but different
# MAGIC    entitlements, so a single blanket rule cannot satisfy them.
# MAGIC 3. **Assess rows are region-scoped**, so column masking alone is not enough —
# MAGIC    rows must be filtered too, and the two mechanisms are different.
# MAGIC
# MAGIC Seeded, so graded answers match everywhere.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — customers with one sensitive column

# COMMAND ----------

rng = random.Random(SEED)
FIRST = ["Ana", "Ben", "Chi", "Dee", "Eli", "Fay", "Gus", "Hana"]
LAST = ["Torres", "Okafor", "Nguyen", "Silva", "Meyer", "Haddad", "Kaur", "Rossi"]

customers = []
for i in range(1, 121):
    f, l = rng.choice(FIRST), rng.choice(LAST)
    customers.append((
        f"CUST-{i:05d}", f"{f} {l}",
        f"{f.lower()}.{l.lower()}{i}@example.com",     # the sensitive column
        rng.choice(["Northeast", "South", "Mountain", "Northwest"]),
        round(rng.uniform(50, 8000), 2),
    ))

spark.createDataFrame(
    customers,
    "customer_id STRING, full_name STRING, email STRING, region STRING, lifetime_value DOUBLE",
).write.mode("overwrite").saveAsTable("s7_teach_customers")

print("teach:", spark.table("s7_teach_customers").count(), "customers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — employee records with three kinds of sensitivity
# MAGIC
# MAGIC | Column | Sensitivity | Needs |
# MAGIC |---|---|---|
# MAGIC | `national_id` | direct identifier | irreversibly hashed for everyone but HR |
# MAGIC | `case_note` | free text, may contain anything | suppressed entirely outside HR |
# MAGIC | `salary` | aggregate-safe, row-unsafe | readable by HR, nulled for others |
# MAGIC | `region` | scoping attribute | rows restricted by the viewer's region |

# COMMAND ----------

rng = random.Random(SEED + 3)
REGIONS = ["emea", "amer", "apac"]
NOTES = [
    "Requested flexible hours from Q2.",
    "Completed compliance training.",
    "Relocation discussed; no decision.",
    "Mentoring two junior engineers.",
    "On extended leave until further notice.",
]

employees = []
for i in range(1, 181):
    f, l = rng.choice(FIRST), rng.choice(LAST)
    employees.append((
        f"EMP-{i:05d}",
        f"{f} {l}",
        f"{rng.randint(100000000, 999999999)}",         # national_id
        rng.choice(REGIONS),
        rng.choice(["engineering", "sales", "support"]),
        float(rng.randrange(45000, 185000, 500)),        # salary
        rng.choice(NOTES),                               # free-text case note
        date(2020, 1, 1) + timedelta(days=rng.randint(0, 2200)),
    ))

spark.createDataFrame(
    employees,
    "employee_id STRING, full_name STRING, national_id STRING, region STRING, "
    "department STRING, salary DOUBLE, case_note STRING, hired_on DATE",
).write.mode("overwrite").saveAsTable("s7_assess_employees")

print("assess:", spark.table("s7_assess_employees").count(), "employees")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the traps are real

# COMMAND ----------

from pyspark.sql import functions as F

emp = spark.table("s7_assess_employees")
teach = spark.table("s7_teach_customers")

sensitive_assess = [c for c in ["national_id", "salary", "case_note"] if c in emp.columns]
sensitive_teach = [c for c in ["email"] if c in teach.columns]

print("teach sensitive columns :", sensitive_teach)
print("assess sensitive columns:", sensitive_assess)
print("assess regions          :", sorted(r["region"] for r in emp.select("region").distinct().collect()))
print("distinct national_ids   :", emp.select("national_id").distinct().count())

assert len(sensitive_assess) > len(sensitive_teach), \
    "assess must protect more kinds of column than teach, or a single teach-style mask suffices"
assert emp.select("region").distinct().count() > 1, \
    "row scoping needs more than one region"
assert emp.select("national_id").distinct().count() == emp.count(), \
    "national_id must be unique, or hashing it proves nothing about re-identification"
print("\ntraps present")
