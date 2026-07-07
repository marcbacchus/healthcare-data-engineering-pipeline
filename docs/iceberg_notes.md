# Apache Iceberg — Point of View

*Phase 3.5 exploration. Self-contained local demo, not a production claim.*

---

## What Iceberg actually is

Iceberg is a **table format specification** sitting on top of files (Parquet,
ORC, Avro). It adds a metadata layer — a catalog + snapshot tree — that gives
you database-like guarantees on plain object storage (S3, ADLS, GCS).

The files themselves don't change. Iceberg wraps them in a snapshot model that
tracks what files belong to each version of the table, which columns exist,
and what the statistics look like for pruning.

---

## What it solves that plain Parquet/Hive doesn't

| Problem | Plain Parquet/Hive | Iceberg |
|---|---|---|
| **Schema evolution** | Adding a column requires rewriting every file or risks corrupt reads | Column added in metadata only — old files read as-is, new column returns NULL for old rows. Zero downtime, zero rewrite. |
| **Time travel** | You'd need to manually archive old file versions | Every write creates a snapshot. `table.scan(snapshot_id=...)` reads any prior state. |
| **ACID on object storage** | No transaction isolation — concurrent writers corrupt the table | Optimistic concurrency via snapshot commit. Each writer proposes a new snapshot; conflicts are detected and retried. |
| **Partition evolution** | Changing partition layout = full rewrite | Can change partition strategy going forward without touching historical files. |
| **File pruning** | Hive partition pruning only — all files in a partition are scanned | Column-level min/max statistics in metadata — scan skips entire files based on predicates before reading any bytes. |

---

## What this demo showed

Running `iceberg/demo.py`:

1. **Schema evolution** — created a 5-column table, loaded 10 FAERS-like rows,
   then added `serious_flag` via `update_schema()`. The 10 existing rows were
   untouched — no files rewritten, no data movement. Old rows return NULL for
   the new column; new rows populate it.

2. **Time travel** — queried `snapshot_id` from before the schema evolution.
   Got exactly 10 rows with 5 columns — the pre-evolution state, as if the
   column addition never happened.

3. **Predicate pushdown** — `row_filter="serious_flag = 'Y'"` passed directly
   to the scan layer. In production on ADLS/S3, Iceberg would use column
   statistics to skip files that can't contain matching rows before reading.

Catalog used: SQLite (local, dev-only). Production catalogs: AWS Glue,
Hive Metastore, Nessie (Git-for-data, multi-table transactions), or
Snowflake's own Iceberg catalog (for Snowflake-managed Iceberg tables).

---

## Where it fits relative to Snowflake and Databricks

```
Snowflake (internal storage)
  └─ Snowflake manages its own proprietary format internally.
     "Snowflake Iceberg tables" = Snowflake writes Iceberg-format files to
     your ADLS/S3 and uses Snowflake as the catalog. Other engines can then
     read those files directly.

Databricks (Delta Lake)
  └─ Delta Lake is Databricks' answer to the same problem — ACID on object
     storage, schema evolution, time travel. Delta and Iceberg are
     functionally equivalent for most use cases. Delta has deeper Spark
     integration; Iceberg has broader cross-engine support.

Iceberg (standalone / open)
  └─ Engine-agnostic. The same Iceberg table can be read by Spark, Trino,
     Flink, Snowflake, DuckDB, PyIceberg. That portability is the main
     argument for it over Delta in multi-engine environments.
```

**The integration point with this project's Snowflake warehouse:**
Snowflake can be configured to read an external Iceberg table stored in ADLS
(the same `sthealthpipeline` storage account from Phase 3) via an external
volume. This would let a Snowflake query hit Iceberg-format files written by
Spark or Databricks — closing the cross-engine read loop without copying data.

Not implemented here (would require a Spark writer and Snowflake external
volume setup), but the pattern is:
```sql
CREATE ICEBERG TABLE external_faers
  EXTERNAL_VOLUME = 'my_adls_volume'
  CATALOG = 'SNOWFLAKE'
  BASE_LOCATION = 'iceberg/faers/';
```

---

## When to reach for Iceberg

**Reach for it when:**
- You have multiple engines reading the same data (Spark + Trino + Snowflake).
  Iceberg's open spec means no vendor lock-in on the file layer.
- You need schema evolution without coordination windows or rewrites — common
  in healthcare where source schemas drift frequently.
- You need audit-grade time travel (regulatory lookback, debugging a bad load).
- You're on a data lakehouse pattern (ADLS/S3 as the source of truth, compute
  engines as readers).

**Don't reach for it when:**
- Snowflake is your only engine and you're not sharing data externally.
  Snowflake's internal format is already ACID, already schema-evolvable,
  already time-travelable (Time Travel feature, up to 90 days). Adding Iceberg
  on top just adds operational surface area.
- Your team is entirely on Databricks. Delta Lake solves the same problems
  with better native Spark integration.
- You're on a pure warehouse pattern with no object storage landing zone.
  Iceberg is a lakehouse primitive — it lives in the lake layer.

---

## Honest assessment

This is a learning exploration, not hands-on production experience. What I can
speak to from this demo:

- The catalog → snapshot → file relationship and how schema evolution works
  at the metadata layer (no data rewrite)
- Time travel mechanics (snapshot IDs, how to query prior state)
- Where Iceberg fits vs. Snowflake's internal tables vs. Delta Lake
- The cross-engine read scenario (Snowflake as Iceberg reader) conceptually

What I haven't done: run Iceberg at scale, managed a production catalog
(Glue, Nessie), dealt with compaction/vacuum on large snapshot histories, or
operated the Snowflake external Iceberg table integration end-to-end.

That's the honest line — I understand the architecture and can discuss the
tradeoffs confidently; I wouldn't claim production expertise.
