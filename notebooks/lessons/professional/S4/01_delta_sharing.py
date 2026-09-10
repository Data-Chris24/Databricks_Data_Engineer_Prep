# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S4 · Delta Sharing
# MAGIC
# MAGIC **Objectives:** `PRO-S4-O1`, `PRO-S4-O3`
# MAGIC
# MAGIC Delta Sharing gives someone else read access to your tables **without copying
# MAGIC them**. No pipeline, no export, no second copy to keep in step — the recipient
# MAGIC reads the same files, governed by your grants.
# MAGIC
# MAGIC Three nouns carry the whole model:
# MAGIC
# MAGIC | Noun | Is | Analogy |
# MAGIC |---|---|---|
# MAGIC | **Share** | a named collection of tables, views and volumes | a playlist |
# MAGIC | **Recipient** | who you are sharing with | the person you sent it to |
# MAGIC | **Grant** | `GRANT SELECT ON SHARE ... TO RECIPIENT ...` | pressing send |
# MAGIC
# MAGIC > **What this workspace can and cannot do.** The provider side runs in full here.
# MAGIC > The consumer side needs a second metastore, and **open-protocol sharing is
# MAGIC > disabled on this metastore** — both are covered as theory, with the exact errors
# MAGIC > printed rather than described.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
CATALOG, SCHEMA = "workspace", "de_prep"
SHARE = "pro_s4_lesson_share"
RECIPIENT = "pro_s4_lesson_recipient"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

spark.sql(f"DROP SHARE IF EXISTS {SHARE}")
for r in w.recipients.list():
    if r.name == RECIPIENT:
        w.recipients.delete(RECIPIENT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A share is a container, and it starts empty

# COMMAND ----------

spark.sql(f"CREATE SHARE {SHARE} COMMENT 'Lesson share for PRO-S4'")
display(spark.sql("SHOW SHARES"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Adding objects — and the traversal rule showing up again
# MAGIC
# MAGIC Owning a table is not enough to share it. `ALTER SHARE ... ADD TABLE` checks
# MAGIC `USE CATALOG` and `USE SCHEMA` explicitly, and a `PERMISSION_DENIED` here is
# MAGIC almost always that, not a problem with the share.

# COMMAND ----------

me = w.current_user.me().user_name
spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{me}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{me}`")

spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_orders")
display(spark.sql(f"SHOW ALL IN SHARE {SHARE}"))

# COMMAND ----------

# MAGIC %md
# MAGIC **`history_sharing` is `ENABLED`.** You did not ask for that. It is the default,
# MAGIC and it means the recipient can time-travel your table and read versions you may
# MAGIC not have meant to publish. Nothing warned you, and the statement that produced it
# MAGIC is the shortest one in the manual.
# MAGIC
# MAGIC Note also the `name` column: the recipient sees `de_prep.pro_s4_teach_orders`,
# MAGIC your schema and table names included. Section 4 fixes that.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. History, and the deletion-vector constraint
# MAGIC
# MAGIC `WITHOUT HISTORY` is how you share only the current state.

# COMMAND ----------

spark.sql(f"ALTER SHARE {SHARE} REMOVE TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_orders")
spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_orders "
          f"WITHOUT HISTORY")

for r in spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect():
    print(f"{r['name']:34} history={r['history_sharing']:9} cdf={r['cdf_shared']}")

# COMMAND ----------

# MAGIC %md
# MAGIC That worked because these tables have **deletion vectors disabled**. When a table
# MAGIC uses deletion vectors, its current state is not reconstructable from data files
# MAGIC alone — the deletes live in the log — so Delta Sharing refuses to share it
# MAGIC without full history.
# MAGIC
# MAGIC The remedy is to stop using the feature and rewrite the files:
# MAGIC
# MAGIC ```sql
# MAGIC ALTER TABLE t SET TBLPROPERTIES (delta.enableDeletionVectors = false);
# MAGIC REORG TABLE t APPLY (PURGE);
# MAGIC ALTER SHARE s ADD TABLE t WITHOUT HISTORY;
# MAGIC ```
# MAGIC
# MAGIC `REORG ... APPLY (PURGE)` is the part people miss. Turning the property off stops
# MAGIC *new* deletion vectors; it does not remove the ones already there.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Change data feed, and a clause that will not work here
# MAGIC
# MAGIC `WITH CHANGE DATA FEED` lets the recipient read *what changed* instead of
# MAGIC re-reading the table. On this metastore the clause is refused outright, and the
# MAGIC reason is worth knowing: tables encrypted with Databricks-managed keys cannot be
# MAGIC shared with a partition spec, a start version, **or** an explicit CDF clause.

# COMMAND ----------

try:
    spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_customers "
              f"AS partner.customers WITH CHANGE DATA FEED")
    print("accepted")
except Exception as e:
    print("refused:")
    print(" ", str(e).split("SQLSTATE")[0][:230].strip())

# COMMAND ----------

# MAGIC %md
# MAGIC ### What actually controls it
# MAGIC
# MAGIC `cdf_shared` follows the **table's own** `delta.enableChangeDataFeed` property.
# MAGIC Turn CDF on at the table and share it normally, and the recipient gets the change
# MAGIC feed — no clause required.
# MAGIC
# MAGIC That is the general shape of this feature: the share is a *view* of properties the
# MAGIC table already has, more than a place to configure them.

# COMMAND ----------

spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_customers "
          "SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_customers "
          f"AS partner.customers")

for r in spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect():
    print(f"{r['name']:26} history={r['history_sharing']:9} cdf={r['cdf_shared']}")

# COMMAND ----------

# MAGIC %md
# MAGIC `AS partner.customers` renames the object *for the recipient* — they never see
# MAGIC your catalog or schema names, so you can reorganise your side without breaking
# MAGIC theirs. Set the alias when you add the table: `ALTER SHARE ... REMOVE TABLE` takes
# MAGIC the **shared** name, not the source path, so an aliased object cannot be removed
# MAGIC by the path you added it from.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Volumes share too
# MAGIC
# MAGIC Not just tables — a volume shares files, which is how you hand over PDFs, images
# MAGIC or anything else that never belonged in a table.

# COMMAND ----------

spark.sql(f"ALTER SHARE {SHARE} ADD VOLUME {CATALOG}.{SCHEMA}.raw")
display(spark.sql(f"SHOW ALL IN SHARE {SHARE}").select("name", "type", "shared_object"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Recipients: who is on the other end
# MAGIC
# MAGIC Two kinds, and the difference decides everything about the setup.
# MAGIC
# MAGIC | | **Databricks-to-Databricks** | **Open protocol** |
# MAGIC |---|---|---|
# MAGIC | Recipient is | another Databricks metastore | anyone with the client |
# MAGIC | Identified by | their **sharing identifier** (`cloud:region:metastore-id`) | nothing — you send them a credential file |
# MAGIC | Auth | `DATABRICKS` | `TOKEN` |
# MAGIC | They read it with | a catalog in their own workspace | pandas, Spark, Power BI, anything speaking the protocol |
# MAGIC | Available here | **yes** | **no** — disabled on this metastore |
# MAGIC
# MAGIC Your own sharing identifier is on the metastore summary:

# COMMAND ----------

summary = w.metastores.summary()
print("sharing identifier :", summary.global_metastore_id)
print("delta_sharing_scope:", summary.delta_sharing_scope)

# COMMAND ----------

# MAGIC %md
# MAGIC `INTERNAL` is what "open sharing is off" looks like. `INTERNAL_AND_EXTERNAL`
# MAGIC would be needed for the open protocol, and it is a metastore-admin setting.

# COMMAND ----------

from databricks.sdk.service.sharing import AuthenticationType

try:
    w.recipients.create(name="pro_s4_open_demo", authentication_type=AuthenticationType.TOKEN)
    print("open recipient created")
    w.recipients.delete("pro_s4_open_demo")
except Exception as e:
    print("open-protocol recipient refused:")
    print(" ", str(e).strip().splitlines()[0])

# COMMAND ----------

# MAGIC %md
# MAGIC ### Creating the D2D recipient
# MAGIC
# MAGIC In real use you paste **their** sharing identifier. Here we use our own, which
# MAGIC creates a valid recipient we can grant to and inspect — it just has nobody on the
# MAGIC other end.

# COMMAND ----------

w.recipients.create(
    name=RECIPIENT,
    authentication_type=AuthenticationType.DATABRICKS,
    data_recipient_global_metastore_id=summary.global_metastore_id,
    comment="Lesson recipient for PRO-S4")

for r in w.recipients.list():
    if r.name.startswith("pro_s4"):
        print(f"{r.name:26} auth={r.authentication_type.value:11} "
              f"target={r.data_recipient_global_metastore_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. The grant is the moment it becomes shared
# MAGIC
# MAGIC Until this statement runs, the share exists and reaches nobody. This is also the
# MAGIC only privilege a share takes: `SELECT`.

# COMMAND ----------

spark.sql(f"GRANT SELECT ON SHARE {SHARE} TO RECIPIENT {RECIPIENT}")
display(spark.sql(f"SHOW GRANTS ON SHARE {SHARE}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. What the recipient does next (theory — needs a second metastore)
# MAGIC
# MAGIC On their side the share arrives as a **provider**, and they mount it as a catalog:
# MAGIC
# MAGIC ```sql
# MAGIC SHOW PROVIDERS;
# MAGIC SHOW SHARES IN PROVIDER `aws:us-east-2:<your-metastore-id>`;
# MAGIC CREATE CATALOG partner_data USING SHARE `<provider>`.`pro_s4_lesson_share`;
# MAGIC SELECT * FROM partner_data.partner.customers;
# MAGIC ```
# MAGIC
# MAGIC From there it is an ordinary catalog: they grant on it, query it, and see your
# MAGIC updates without a copy step. We cannot run it here — sharing to your own
# MAGIC metastore does not produce a provider:

# COMMAND ----------

print("providers visible to us:", [p.name for p in w.providers.list()] or "none")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. A share is a dependency
# MAGIC
# MAGIC Once an object is in a share, it cannot be dropped. Unity Catalog refuses with
# MAGIC `DELTA_SHARING_SECURABLE_DELETE_BLOCKED.BY_SHARES`, because dropping it would
# MAGIC break a recipient you may not be in contact with.
# MAGIC
# MAGIC This is the same shape of guardrail as a connection that a foreign catalog is
# MAGIC built on, and it is worth knowing before a migration rather than during one.

# COMMAND ----------

try:
    spark.sql(f"DROP TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_orders")
    print("dropped - it was not shared after all")
except Exception as e:
    print("refused:")
    print(" ", str(e).split("SQLSTATE")[0][:200].strip())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Auditing what you have shared
# MAGIC
# MAGIC The question a sharing review asks is not "what is in the share" but **"who can
# MAGIC read what"** — which needs both halves.

# COMMAND ----------

objects = spark.sql(f"SHOW ALL IN SHARE {SHARE}")
grants = spark.sql(f"SHOW GRANTS ON SHARE {SHARE}")
print(f"{objects.count()} objects reachable by {grants.count()} recipient(s)")
display(objects.select("name", "type", "history_sharing", "cdf_shared"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recap
# MAGIC
# MAGIC | Want | Statement |
# MAGIC |---|---|
# MAGIC | A container | `CREATE SHARE s` |
# MAGIC | Add a table | `ALTER SHARE s ADD TABLE c.s.t` — **history ENABLED by default** |
# MAGIC | Current state only | `... WITHOUT HISTORY` — needs deletion vectors off |
# MAGIC | Rename for the recipient | `... AS alias.name` |
# MAGIC | Share changes | `... WITH CHANGE DATA FEED` — needs CDF on the table |
# MAGIC | Files | `ALTER SHARE s ADD VOLUME c.s.v` |
# MAGIC | Send it | `GRANT SELECT ON SHARE s TO RECIPIENT r` |
# MAGIC | Check it | `SHOW ALL IN SHARE s` **and** `SHOW GRANTS ON SHARE s` |

# COMMAND ----------

spark.sql(f"DROP SHARE IF EXISTS {SHARE}")
for r in w.recipients.list():
    if r.name == RECIPIENT:
        w.recipients.delete(RECIPIENT)
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_teach_customers "
          "SET TBLPROPERTIES (delta.enableChangeDataFeed = false)")
print("cleaned up")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_federation](./02_federation).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S4 assignment notebook](../../../assignments/PRO-S4/assignment) · [the task](../../../assignments/PRO-S4/README.md).
