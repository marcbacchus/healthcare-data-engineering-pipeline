# Phase 1 — Raw Ingest Pipeline

Python scripts that load public healthcare data into `HEALTHCARE_RAW.RAW` in Snowflake.

## Design

Every source column is stored as `VARCHAR` — no type casting at this layer. Type
enforcement happens in dbt staging models (Phase 2) via `TRY_TO_DATE()` / `NULLIF()`.
This means source format changes never break the ingest pipeline.

Three metadata columns are appended to every table on load:

| Column | Type | Purpose |
|---|---|---|
| `_loaded_at` | VARCHAR | UTC timestamp of the load run |
| `_source_file` | VARCHAR | Source identifier (API endpoint, filename) |
| `_row_hash` | VARCHAR | MD5 over source columns — enables deduplication |

All loads are **idempotent** — each script truncates the target table before loading,
so re-running produces the same table state.

## Tables

| Table | Source | Rows | Script |
|---|---|---|---|
| `CMS_OPEN_PAYMENTS` | CMS 2023 General Payments via DKAN API | 100,000 | `load_cms.py` |
| `FAERS_DEMO` | FDA FAERS Q4 2024 via openFDA REST API | 26,000 | `load_faers.py` |
| `SYNTHEA_PATIENTS` | Synthea-generated synthetic patients | 1,161 | `load_synthea.py` |
| `SYNTHEA_CONDITIONS` | Synthea-generated conditions (SNOMED-CT) | 42,639 | `load_synthea.py` |

## Setup and usage

```bash
# from project root
cp .env.example .env        # fill in Snowflake credentials + CMS dataset ID

cd ingest/
bash setup_synthea.sh       # download Synthea jar, generate 1K synthetic patients
python load_synthea.py
python load_cms.py
python load_faers.py
```

After loading, run `validate.sql` in Snowflake to confirm row counts and metadata integrity.

## Files

| File | Purpose |
|---|---|
| `snowflake_utils.py` | Shared connection, metadata, and load helpers |
| `load_cms.py` | CMS Open Payments ingest via DKAN API |
| `load_faers.py` | FDA FAERS demographics ingest via openFDA REST API |
| `load_synthea.py` | Synthea patient + conditions CSV ingest |
| `setup_synthea.sh` | Downloads Synthea jar and generates synthetic patient data |
| `validate.sql` | Row count and metadata integrity checks |
| `ddl/` | DDL for the 4 raw tables (reference — provisioned via Terraform) |
| `requirements.txt` | Python dependencies |
