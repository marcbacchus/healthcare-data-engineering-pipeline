# Healthcare Data Engineering Pipeline

A modern enterprise data platform built end-to-end — ingestion, transformation,
orchestration, ML, and an AI assistant — using public healthcare datasets.

Built as a portfolio project demonstrating production-grade patterns across
the full data engineering stack.

---

## Architecture

| Layer | Tool | Role |
|---|---|---|
| Warehouse | Snowflake | Source of truth, query engine |
| Ingestion mechanism | Snowpipe + external stages | Files into Snowflake |
| Infrastructure as code | Terraform | Provisions Snowflake objects |
| Cloud orchestration | Azure Data Factory | Production ingestion pipeline |
| Raw landing zone | Azure Data Lake Storage Gen2 | Staging area before Snowflake load |
| Secrets | Azure Key Vault | Credentials for ADF / Databricks |
| Local orchestration | Airflow (Docker) | Same pipeline rebuilt locally — orchestrator comparison |
| Transformation | dbt | Staging → mart models, tests, docs |
| CI/CD | GitHub Actions | dbt tests on PR, Terraform plan validation |
| Feature engineering + ML | Databricks + MLflow | Feature Store, model training, experiment tracking |
| Model serving | Databricks Model Serving | Live REST endpoint (readmission risk) |
| AI assistant | LangChain + ChromaDB | RAG agent — text-to-SQL, risk scoring, clinical reference |
| Demo UI | Streamlit + Azure Container Apps | Public-facing interface |

---

## Data Sources

All public or synthetic — no proprietary or PHI data.

| Source | Description |
|---|---|
| [CMS Open Payments](https://openpaymentsdata.cms.gov/) | Pharma → physician payments (public CSV) |
| [FDA FAERS](https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/faers-public-dashboard) | Adverse event reports |
| [Synthea](https://synthea.mitre.org/) | Synthetic patient records (generated locally) |

---

## Project Structure

```
├── terraform/            # Snowflake infra as code (Phase 1)
├── ingest/               # Python ingest scripts (Phase 1)
├── azure/
│   ├── adf/              # ADF pipeline JSON exports (Phase 3)
│   └── arm/              # ARM templates for full infra reproducibility
├── airflow/              # Local Airflow DAG (Docker) — orchestrator comparison
├── dbt/                  # dbt project — staging → marts (Phase 2)
├── .github/workflows/    # CI/CD — dbt tests on PR, Terraform plan validation
├── notebooks/            # Databricks notebooks (exported HTML, Phase 4)
├── agent/                # LangChain RAG agent + Streamlit app (Phase 5)
├── docs/                 # Architecture diagrams, data dictionary, model cards
└── data/                 # Sample/raw data (gitignored if large)
```

---

## Phases

| Phase | Focus | Status |
|---|---|---|
| 1 | Snowflake Foundation + Terraform + Raw Ingest | ✅ Complete — 554K rows across 4 raw tables |
| 2 | dbt — staging through marts + CI/CD | Planned |
| 3 | Azure orchestration + Airflow comparison | Planned |
| 4 | Databricks + MLflow | Planned |
| 5 | RAG agent + Streamlit UI | Planned |

---

## Phase 1 — Snowflake Foundation + Raw Ingest

### Week 1: Terraform

Everything is provisioned as code — no manual UI clicks.

**What's provisioned via Terraform (`terraform/`):**

- 3 databases: `HEALTHCARE_RAW`, `HEALTHCARE_TRANSFORM`, `HEALTHCARE_REPORTING`
- 4 schemas: `RAW`, `STAGING`, `MARTS`, `REPORTING`
- 1 warehouse: `COMPUTE_WH` (X-SMALL, auto-suspend 60s, auto-resume)
- 3 roles with least-privilege grants:
  - `LOADER` — writes raw data into `HEALTHCARE_RAW`
  - `TRANSFORMER` — runs dbt, reads RAW, writes STAGING/MARTS
  - `REPORTER` — SELECT-only on marts (BI tools, analysts)

This role hierarchy mirrors the minimum-necessary-access pattern used in
regulated healthcare environments — the same pattern whether the data is
synthetic or production PHI.

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# fill in your Snowflake account credentials

terraform init
terraform plan
terraform apply
```

### Week 2: Raw Ingest Pipeline

Four raw tables loaded into `HEALTHCARE_RAW.RAW` via Python (`ingest/`).

**Design:** every source column stored as `VARCHAR` — no type casting at this
layer. Type enforcement happens in dbt staging models (Phase 2) via
`TRY_TO_DATE()` / `NULLIF()`. Three metadata columns on every table:
`_loaded_at`, `_source_file`, `_row_hash` (MD5 for deduplication).

| Table | Source | Rows |
|---|---|---|
| `CMS_OPEN_PAYMENTS` | CMS 2023 General Payments via DKAN API | 100,000 |
| `FAERS_DEMO` | FDA FAERS Q4 2024 via openFDA REST API | 25,000 |
| `SYNTHEA_PATIENTS` | Synthea-generated synthetic patients | 1,161 |
| `SYNTHEA_CONDITIONS` | Synthea-generated conditions (SNOMED-CT) | 42,639 |

```bash
cd ingest/
cp .env.example .env        # fill in Snowflake credentials + CMS dataset ID
bash setup_synthea.sh       # download Synthea jar, generate 1K patients
python load_synthea.py
python load_cms.py
python load_faers.py
# run validate.sql in Snowflake to confirm row counts and metadata integrity
```

---

## Key Design Decisions

**Why Terraform instead of UI clicks?**
The warehouse config lives in git, changes go through PR review, and the
environment can be torn down and rebuilt reproducibly. Required in any
serious data platform role.

**Why this role structure?**
LOADER / TRANSFORMER / REPORTER enforces a one-way data flow at the
permission level. dbt (TRANSFORMER) cannot modify raw data. BI tools
(REPORTER) cannot break anything upstream. This is the medallion-adjacent
security pattern used at most enterprise Snowflake deployments.

**Why VARCHAR everything in the raw layer?**
Type enforcement at load time causes hard failures when a source changes
format. The raw layer absorbs data as-is; dbt staging handles casting with
graceful fallbacks. Schema drift never breaks the ingest pipeline.

---

*Built with public data. Architecture mirrors production-grade enterprise patterns.*
