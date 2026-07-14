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
├── dbt/                  # dbt project — staging → marts (Phase 2)
├── .github/workflows/    # CI/CD — dbt tests on PR, Terraform plan validation (Phase 2)
├── azure/
│   ├── adf/              # ADF pipeline JSON exports (Phase 3)
│   └── arm/              # ARM templates for full infra reproducibility (Phase 3)
├── airflow/              # Local Airflow DAG (Docker) — orchestrator comparison (Phase 3)
├── notebooks/            # Databricks notebooks — Python source format (Phase 4)
├── agent/                # LangChain RAG agent + Streamlit app (Phase 5)
└── docs/                 # Architecture diagrams, data dictionary, model cards
```

---

## Phases

| Phase | Focus | Status | Details |
|---|---|---|---|
| 1 | Snowflake Foundation + Terraform + Raw Ingest | ✅ Complete — 170K rows across 4 raw tables | [terraform/](terraform/) · [ingest/](ingest/) |
| 2 | dbt — staging through marts + CI/CD | ✅ Complete — 7 models, 22 tests, CI on every PR | [dbt/](dbt/) |
| 3 | Azure orchestration + Airflow comparison | ✅ Complete — ADF pipeline, ADLS Gen2, Key Vault, Snowpipe COPY INTO, Airflow DAG, ARM export, tradeoff writeup | [azure/](azure/) · [airflow/](airflow/) |
| 3.5 | Apache Iceberg exploration | ✅ Complete — local table, schema evolution, time travel, documented POV | [iceberg/](iceberg/) · [docs/iceberg_notes.md](docs/iceberg_notes.md) |
| 4 | Databricks + MLflow | ✅ Complete — Feature Store (8 features), 2 MLflow models, live REST endpoint | [notebooks/](notebooks/) · [docs/model_cards.md](docs/model_cards.md) |
| 5 | RAG agent + Streamlit UI | Planned | [agent/](agent/) |

---

**Docs:** [Architecture diagram](docs/architecture.md) · [Data dictionary](docs/data_dictionary.md) · [dbt docs](https://marcbacchus.github.io/healthcare-data-engineering-pipeline/) *(live after Phase 2 merge)*

*Built with public data. Architecture mirrors production-grade enterprise patterns.*
