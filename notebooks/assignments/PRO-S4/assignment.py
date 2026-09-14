# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S4 — Data Sharing and Federation assignment
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S4` Data Sharing and Federation
# MAGIC
# MAGIC **Objectives:** `PRO-S4-O1`, `PRO-S4-O2`, `PRO-S4-O3`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work both lessons in `notebooks/lessons/professional/S4/`, and build the objects
# MAGIC (`databricks bundle run generate_datasets_pro_s4 -t free`).
# MAGIC
# MAGIC > **In the lesson, the tables shared however you asked.** Deletion vectors were off,
# MAGIC > so `WITHOUT HISTORY` just worked, and one statement per table was enough. Three of
# MAGIC > the four objects here will not cooperate on the first attempt.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC You are the provider. A partner is being onboarded, and legal has been specific.
# MAGIC Configure it, exactly.
# MAGIC
# MAGIC #### The share — `pro_s4_partner_share`
# MAGIC
# MAGIC | Source | Shared as | Terms |
# MAGIC |---|---|---|
# MAGIC | `workspace.de_prep.pro_s4_assess_orders` | `partner.orders` | **no history** — current state only |
# MAGIC | `workspace.de_prep.pro_s4_assess_customers` | `partner.customers` | history **kept** |
# MAGIC | `workspace.de_prep.pro_s4_assess_events` | `partner.events` | the partner needs the **change feed** |
# MAGIC | `workspace.de_prep.pro_s4_assess_files` (volume) | `partner.files` | — |
# MAGIC | `workspace.de_prep.pro_s4_assess_salaries` | — | **must not be shared** |
# MAGIC
# MAGIC #### The recipient — `pro_s4_partner`
# MAGIC
# MAGIC - Databricks-to-Databricks. There is no second metastore here, so target **this**
# MAGIC   workspace's own sharing identifier — read it from the metastore summary rather
# MAGIC   than typing it.
# MAGIC - Granted `SELECT` on the share, and nothing else granted to anyone else.
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **Every object is aliased into `partner.`** The partner must not see your catalog
# MAGIC    or schema names. Set the alias when you add the object — `REMOVE TABLE` takes the
# MAGIC    *shared* name, so this is not fixable afterwards from the source path.
# MAGIC 2. **`partner.orders` must carry no history.** The shortest statement gives you
# MAGIC    history, silently.
# MAGIC 3. **`partner.events` must share its change feed.** The clause you would reach for
# MAGIC    first is refused here; find what actually controls it.
# MAGIC 4. **`pro_s4_assess_salaries` must not be reachable through any share.** There is
# MAGIC    nothing to write for this requirement, which is why it is the one that gets missed.
# MAGIC 5. Nothing about a wrong answer here raises an error. Check the configuration you
# MAGIC    produced, don't assume it.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s4 -t free
# MAGIC ```
# MAGIC
# MAGIC The tests read the live configuration — the share's contents and terms, the
# MAGIC recipient, and the grants. The advisory AI review (`grading/rubrics/PRO-S4.yaml`)
# MAGIC judges whether you understood *why* each object needed different handling.
# MAGIC
# MAGIC ### What Free Edition cannot do here
# MAGIC
# MAGIC Measured, not assumed — see `docs/free-edition-constraints.md`:
# MAGIC
# MAGIC - **Open-protocol sharing is disabled** on this metastore, so `TOKEN` recipients
# MAGIC   cannot be created. `PRO-S4-O3` is theory here.
# MAGIC - **The consumer side needs a second metastore.** Sharing to your own metastore
# MAGIC   produces no provider, so `CREATE CATALOG ... USING SHARE` cannot be run.
# MAGIC - **Lakehouse Federation's query path does not work.** Connections, foreign catalogs
# MAGIC   and their grants all succeed; the first query fails with `FAILED_JDBC.CONNECTION`,
# MAGIC   including against this workspace's own SQL warehouse. `PRO-S4-O2` is hands-on for
# MAGIC   everything except reading data through it.
# MAGIC
# MAGIC ### Cleaning up
# MAGIC
# MAGIC ```sql
# MAGIC DROP SHARE pro_s4_partner_share;
# MAGIC ```
# MAGIC then delete the recipient (`databricks recipients delete pro_s4_partner`). Note a
# MAGIC table cannot be dropped while it is in a share — remove it from the share first.
# MAGIC <!-- task:end -->

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sharing import AuthenticationType

w = WorkspaceClient()
CATALOG, SCHEMA = "workspace", "de_prep"
SHARE, RECIPIENT = "pro_s4_partner_share", "pro_s4_partner"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Look at what you have been given
# MAGIC
# MAGIC Check each table's properties before you try to share it. Two properties decide
# MAGIC what terms are available to you.

# COMMAND ----------

for t in ("pro_s4_assess_orders", "pro_s4_assess_customers",
          "pro_s4_assess_events", "pro_s4_assess_salaries"):
    props = {r["key"]: r["value"] for r in spark.sql(f"SHOW TBLPROPERTIES {t}").collect()}
    print(f"{t:28} DV={props.get('delta.enableDeletionVectors', '-'):6} "
          f"CDF={props.get('delta.enableChangeDataFeed', '-')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The share

# COMMAND ----------

# TODO


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Add the objects, each on its own terms

# COMMAND ----------

# TODO


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The recipient, and the grant

# COMMAND ----------

# TODO


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Check what you actually built
# MAGIC
# MAGIC Read `history_sharing` and `cdf_shared` for every row, and confirm the one table
# MAGIC that must not be shared is absent. Both failures are silent.

# COMMAND ----------

display(spark.sql(f"SHOW ALL IN SHARE {SHARE}")
        .select("name", "type", "history_sharing", "cdf_shared", "shared_object"))
display(spark.sql(f"SHOW GRANTS ON SHARE {SHARE}"))
