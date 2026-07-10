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

## Phase 4 Detail: Databricks + MLflow

### Feature Engineering
- Connected Databricks to Snowflake using the TRANSFORMER role (least privilege)
- Read `mart_patient_risk` from the governed dbt mart layer — same data the business uses, eliminating training/serving skew at the source
- Engineered 8 features; 7 passed through from the dbt mart, 1 (`expense_to_income_ratio`) derived in Databricks as a model-specific transformation
- Registered feature table in Databricks Feature Store (Unity Catalog) with `patient_id` as primary key

### Models

**Readmission Risk (XGBoost)**
- Training set built via `fe.create_training_set()` + `FeatureLookup` — feature store pattern, not a raw table read
- Synthetic proxy label (Synthea has no real readmission outcomes) — documented honestly in model card
- Dual-threshold logging: 0.35 (high sensitivity, minimize missed high-risk patients) and 0.50 (balanced)
- AUC 0.512 expected on synthetic label — architecture is production-ready, label is a learning stand-in
- Deployed to **Databricks Model Serving** (serverless, scale-to-zero) — live REST endpoint returning binary predictions

**Provider Payment Anomaly (IsolationForest)**
- Unsupervised anomaly detection on 100K CMS Open Payments records
- 4,994 anomalies flagged at 5% contamination — top flag: $191K single-provider payment
- Logged to MLflow with sklearn signature; registered in Unity Catalog

**Adverse Event Severity (Random Forest) — dropped**
- FAERS demographic fields entirely null; insufficient signal for classification
- Documented in model card with path to revival (FAERS OUTC outcome file)
- Roadmap explicitly planned this as the first trim if needed

### Notebooks
| Notebook | Purpose |
|----------|---------|
| [phase4_feature_engineering.py](notebooks/phase4_feature_engineering.py) | Snowflake → Feature Store |
| [phase4_mlflow_training.py](notebooks/phase4_mlflow_training.py) | XGBoost training + MLflow logging |
| [phase4_models_2_3.py](notebooks/phase4_models_2_3.py) | IsolationForest payment anomaly |
| [phase4_model_serving.py](notebooks/phase4_model_serving.py) | Serving endpoint + REST test |

**Model cards:** [docs/model_cards.md](docs/model_cards.md) — intended use, metrics, threshold rationale, limitations, bias considerations for each model.

---

**Docs:** [Architecture diagram](docs/architecture.md) · [Data dictionary](docs/data_dictionary.md) · [dbt docs](https://marcbacchus.github.io/healthcare-data-engineering-pipeline/) *(live after Phase 2 merge)*

*Built with public data. Architecture mirrors production-grade enterprise patterns.*
