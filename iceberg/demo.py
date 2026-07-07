"""
Phase 3.5 — Apache Iceberg Exploration

Demonstrates the two features that make Iceberg valuable over plain Parquet/Hive:
  1. Schema evolution  — add a column without rewriting existing data
  2. Time travel       — query any prior snapshot by ID or timestamp

Data: a small slice of FAERS-like adverse event records (self-contained, no
Snowflake dependency). Same shape as fct_adverse_events from Phase 2 dbt mart.

Run: python iceberg/demo.py
"""

import os
import shutil
from pathlib import Path

import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    LongType,
    NestedField,
    StringType,
)

# ---------------------------------------------------------------------------
# Setup — local SQLite catalog + file-based warehouse (both gitignored)
# ---------------------------------------------------------------------------

ICEBERG_DIR = Path(__file__).parent
CATALOG_URI = f"sqlite:///{ICEBERG_DIR}/catalog/healthcare.db"
WAREHOUSE_PATH = str(ICEBERG_DIR / "warehouse")

# Clean slate on every run so the demo is repeatable
for d in ["catalog", "warehouse"]:
    target = ICEBERG_DIR / d
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

catalog = SqlCatalog(
    "healthcare",
    **{
        "uri": CATALOG_URI,
        "warehouse": WAREHOUSE_PATH,
    },
)

catalog.create_namespace("healthcare")

# ---------------------------------------------------------------------------
# Initial schema — mirrors fct_adverse_events from the dbt mart
# ---------------------------------------------------------------------------

schema = Schema(
    NestedField(1, "report_id",   StringType()),
    NestedField(2, "drug_name",   StringType()),
    NestedField(3, "reaction",    StringType()),
    NestedField(4, "event_date",  StringType()),
    NestedField(5, "age_years",   LongType()),
)

table = catalog.create_table("healthcare.fct_adverse_events", schema=schema)

print("=" * 60)
print("PHASE 3.5 — Apache Iceberg Demo")
print("=" * 60)
print(f"\nCatalog  : SQLite ({CATALOG_URI})")
print(f"Warehouse: {WAREHOUSE_PATH}")
print(f"\nInitial schema ({len(schema.fields)} columns):")
for f in schema.fields:
    print(f"  {f.field_id:>2}. {f.name:<15} {str(f.field_type):<15}")

# ---------------------------------------------------------------------------
# Snapshot 1 — write 10 initial records (no serious_flag column yet)
# ---------------------------------------------------------------------------

batch_1 = pa.table({
    "report_id":  ["FAE001", "FAE002", "FAE003", "FAE004", "FAE005",
                   "FAE006", "FAE007", "FAE008", "FAE009", "FAE010"],
    "drug_name":  ["METFORMIN", "LISINOPRIL", "ATORVASTATIN", "METFORMIN",
                   "AMLODIPINE", "OMEPRAZOLE", "METFORMIN", "LISINOPRIL",
                   "ATORVASTATIN", "AMLODIPINE"],
    "reaction":   ["NAUSEA", "DRY COUGH", "MUSCLE PAIN", "DIARRHEA",
                   "EDEMA", "HEADACHE", "VOMITING", "DIZZINESS",
                   "LIVER ENZYME ELEVATION", "FLUSHING"],
    "event_date": ["2023-01-15", "2023-02-01", "2023-02-14", "2023-03-05",
                   "2023-03-22", "2023-04-10", "2023-04-18", "2023-05-07",
                   "2023-05-19", "2023-06-03"],
    "age_years":  [67, 54, 72, 58, 81, 45, 63, 70, 55, 77],
})

table.append(batch_1)
snapshot_1_id = table.current_snapshot().snapshot_id
snapshot_1_ts  = table.current_snapshot().timestamp_ms

print(f"\n{'─'*60}")
print(f"SNAPSHOT 1 — initial load (10 rows, 5 columns)")
print(f"  snapshot_id : {snapshot_1_id}")
print(f"  row count   : {table.scan().to_arrow().num_rows}")

# ---------------------------------------------------------------------------
# Schema evolution — add serious_flag without rewriting any existing data
# ---------------------------------------------------------------------------

print(f"\n{'─'*60}")
print("SCHEMA EVOLUTION — adding column: serious_flag (StringType, optional)")

with table.update_schema() as update:
    update.add_column("serious_flag", StringType())

print(f"  Schema now has {len(table.schema().fields)} columns:")
for f in table.schema().fields:
    print(f"  {f.field_id:>2}. {f.name:<15} {str(f.field_type):<15}")

print("  Existing rows are UNAFFECTED — no data rewrite, no downtime.")
print("  Old rows will return NULL for serious_flag (schema default).")

# ---------------------------------------------------------------------------
# Snapshot 2 — write 5 more records that include serious_flag
# ---------------------------------------------------------------------------

batch_2 = pa.table({
    "report_id":   ["FAE011", "FAE012", "FAE013", "FAE014", "FAE015"],
    "drug_name":   ["WARFARIN", "INSULIN GLARGINE", "METFORMIN",
                    "LISINOPRIL", "WARFARIN"],
    "reaction":    ["BLEEDING", "HYPOGLYCEMIA", "LACTIC ACIDOSIS",
                    "RENAL FAILURE", "INTRACRANIAL HEMORRHAGE"],
    "event_date":  ["2023-06-15", "2023-07-02", "2023-07-18",
                    "2023-08-05", "2023-08-22"],
    "age_years":   [74, 68, 82, 59, 71],
    "serious_flag": ["Y", "Y", "Y", "Y", "Y"],
})

table.append(batch_2)
snapshot_2_id = table.current_snapshot().snapshot_id

print(f"\n{'─'*60}")
print(f"SNAPSHOT 2 — incremental load (5 rows with serious_flag populated)")
print(f"  snapshot_id : {snapshot_2_id}")
print(f"  row count   : {table.scan().to_arrow().num_rows}")

# ---------------------------------------------------------------------------
# Current state — all 15 rows, serious_flag NULL for old rows
# ---------------------------------------------------------------------------

print(f"\n{'─'*60}")
print("CURRENT STATE — all 15 rows (serious_flag NULL on pre-evolution rows):")
current = table.scan().to_arrow()
for col in ["report_id", "drug_name", "reaction", "age_years", "serious_flag"]:
    col_data = current.column(col)
    print(f"  {col:<18}: {col_data[:5].to_pylist()} ...")

print(f"\n  Serious events only (serious_flag = 'Y'):")
serious = table.scan(
    row_filter="serious_flag = 'Y'"
).to_arrow()
print(f"  {serious.column('report_id').to_pylist()}")
print(f"  {serious.column('reaction').to_pylist()}")

# ---------------------------------------------------------------------------
# Time travel — query snapshot 1 (before schema evolution)
# ---------------------------------------------------------------------------

print(f"\n{'─'*60}")
print(f"TIME TRAVEL — querying snapshot 1 (snapshot_id={snapshot_1_id})")
print(f"  This is the state BEFORE serious_flag was added.")

old = table.scan(snapshot_id=snapshot_1_id).to_arrow()
print(f"  Row count   : {old.num_rows}  (only original 10)")
print(f"  Column names: {old.schema.names}")
print(f"  report_ids  : {old.column('report_id').to_pylist()}")

# ---------------------------------------------------------------------------
# Snapshot history
# ---------------------------------------------------------------------------

print(f"\n{'─'*60}")
print("SNAPSHOT HISTORY:")
for entry in table.history():
    snap = table.snapshot_by_id(entry.snapshot_id)
    op = snap.summary.get("operation", "unknown") if snap and snap.summary else "unknown"
    print(f"  snapshot_id={entry.snapshot_id}  ts={entry.timestamp_ms}  op={op}")

print(f"\n{'─'*60}")
print("DONE — what this demonstrates:")
print("  ✓ Schema evolution  : added serious_flag without rewriting 10 existing rows")
print("  ✓ Time travel       : queried pre-evolution snapshot by snapshot_id")
print("  ✓ ACID append       : two independent snapshots, each consistent")
print("  ✓ Predicate pushdown: row_filter='serious_flag = Y' pushed to scan layer")
print("=" * 60)
