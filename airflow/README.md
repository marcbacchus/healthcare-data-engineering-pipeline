# Phase 3 — Airflow: Local DAG (Orchestrator Comparison)

A local Airflow implementation of the same ingestion pipeline built in Azure Data
Factory (Phase 3). This is a **comparison exercise, not a second production system** —
the purpose is to demonstrate orchestrator-agnostic understanding by rebuilding the
same logical pipeline in a code-first, DAG-as-code style.

---

## What This Does

Replicates the ADF `pl_ingest_healthcare` pipeline as a local Airflow DAG running
in Docker. Same three logical steps:

1. **Resolve CMS download URL** — dynamic lookup from DKAN metastore (CMS refreshes the file path on each dataset update)
2. **Download and upload to ADLS** — CMS CSV and FAERS JSON fetched in parallel, uploaded to Azure Data Lake Storage Gen2 (`raw/cms/` and `raw/faers/`)
3. **Snowflake COPY INTO** — loads each source from the external stage into the raw Snowflake tables

---

## Contents

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Spins up Airflow (webserver + scheduler + postgres metadata DB) |
| `requirements.txt` | Python dependencies for the DAG |
| `dags/healthcare_ingest_dag.py` | The DAG — mirrors ADF pipeline logic step for step |
| `logs/` | Airflow task logs (gitignored) |
| `plugins/` | Empty — no custom plugins used |

---

## How to Run Locally

```bash
cd airflow
docker compose up -d
```

Then open `http://localhost:8080` (default credentials: `airflow` / `airflow`).

Set the following environment variables in `docker-compose.yml` before running:
- `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`
- `ADLS_ACCOUNT_NAME`, `ADLS_ACCOUNT_KEY`
- `CMS_DATASET_ID`

Trigger the `healthcare_ingest` DAG manually from the UI or wait for the scheduled run.

---

## ADF vs. Airflow — Key Tradeoffs

| Dimension | Azure Data Factory | Airflow (local) |
|-----------|-------------------|-----------------|
| Pipeline definition | GUI + JSON | Python code (DAG file) |
| Version control | ARM template export | Native (DAG is a .py file) |
| Scheduling | Built-in triggers | Cron expression in DAG |
| Monitoring | Azure Monitor + alerts | Airflow UI + task logs |
| Infrastructure | Fully managed (Azure) | Self-hosted (Docker here) |
| Best for | Cloud-native, low-code teams | Code-first, complex dependency graphs |

**When to reach for Airflow over ADF:** complex branching logic, heavy Python
transformation steps, teams that prefer code review over GUI config, or
multi-cloud / on-prem environments where Azure lock-in is a concern.

Full tradeoff writeup: [azure/adf/README.md](../azure/adf/README.md)
