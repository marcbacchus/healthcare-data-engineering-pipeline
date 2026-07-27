# Healthcare Data Engineering Pipeline

A modern enterprise data platform built end-to-end — ingestion, transformation,
orchestration, ML, and an AI assistant — using public healthcare datasets.

Built as a portfolio project demonstrating production-grade patterns across
the full data engineering stack.

**Live demo:** https://ca-healthcare-agent.victoriousmeadow-ffdf677d.eastus.azurecontainerapps.io
— a LangChain ReAct agent with three tools (Snowflake text-to-SQL, RAG over
adverse event reports, a live Databricks readmission-risk endpoint), deployed
at true scale-to-zero. See [docs/evaluation.md](docs/evaluation.md) for an
honest 8/10 evaluation, misses included.

---

## Architecture

| Layer | Tool | Role |
|---|---|---|
| Warehouse | Snowflake | Source of truth, query engine |
| Ingestion mechanism | External stage + COPY INTO | Files into Snowflake |
| Infrastructure as code | Terraform | Provisions Snowflake objects |
| Cloud orchestration | Azure Data Factory | Production ingestion pipeline |
| Raw landing zone | Azure Data Lake Storage Gen2 | Staging area before Snowflake load |
| Secrets | Azure Key Vault | Credentials for ADF / Databricks |
| Local orchestration | Airflow (Docker) | Same pipeline rebuilt locally — orchestrator comparison |
| Open table format | Apache Iceberg | Standalone exploration — schema evolution, time travel |
| Transformation | dbt | Staging → mart models, tests, docs |
| CI/CD | GitHub Actions | dbt tests on PR, Terraform plan validation |
| Feature engineering + ML | Databricks + MLflow | Feature Store, model training, experiment tracking |
| Model serving | Databricks Model Serving | Live REST endpoint (readmission risk) |
| AI assistant | LangChain + ChromaDB | RAG agent — text-to-SQL, adverse event RAG, risk scoring |
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
├── iceberg/              # Apache Iceberg exploration — schema evolution, time travel (Phase 3.5)
├── notebooks/            # Databricks notebooks — Python source format (Phase 4)
├── agent/                # LangChain RAG agent + Streamlit app (Phase 5)
└── docs/                 # Architecture diagrams, data dictionary, model cards
```

---

## Phases

| Phase | Focus | Status | Details |
|---|---|---|---|
| 1 | Snowflake Foundation + Terraform + Raw Ingest | ✅ Complete — 170K rows across 4 raw tables | [terraform/](terraform/) · [ingest/](ingest/) |
| 2 | dbt — staging through marts + CI/CD | ✅ Complete — 7 models, 24 tests, CI on every PR | [dbt/](dbt/) |
| 3 | Azure orchestration + Airflow comparison | ✅ Complete — ADF pipeline, ADLS Gen2, Key Vault, external stage + COPY INTO, Airflow DAG, ARM export, tradeoff writeup | [azure/](azure/) · [airflow/](airflow/) |
| 3.5 | Apache Iceberg exploration | ✅ Complete — local table, schema evolution, time travel, documented POV | [iceberg/](iceberg/) · [docs/iceberg_notes.md](docs/iceberg_notes.md) |
| 4 | Databricks + MLflow | ✅ Complete — Feature Store (8 features), 2 MLflow models, live REST endpoint | [notebooks/](notebooks/) · [docs/model_cards.md](docs/model_cards.md) |
| 5 | RAG agent + Streamlit UI | ✅ Complete — 3 tools, ReAct agent w/ memory, Docker, live on Azure Container Apps, 8/10 eval | [agent/](agent/) · [docs/evaluation.md](docs/evaluation.md) |

---

**Docs:** [Architecture diagram](docs/architecture.md) · [Data dictionary](docs/data_dictionary.md) · [Model cards](docs/model_cards.md) · [Iceberg notes](docs/iceberg_notes.md) · [Agent evaluation](docs/evaluation.md) · [dbt docs](https://marcbacchus.github.io/healthcare-data-engineering-pipeline/)

---

## What I'd Add Next

Honest gaps, not a wish list — each ties to something specific found while building or evaluating this:

- **Tool-selection tightening (from evaluation.md #6):** the agent sometimes asks
  a clarifying question instead of trying the most relevant tool first, so the
  user never sees that tool's own honest "this data isn't loaded" answer.
  Fix is scoped: bias the system prompt toward "try first, clarify only if the
  tool itself can't proceed."
- **No-fallback-reasoning guardrail (from evaluation.md #7):** on a Databricks
  cold-start timeout, the agent correctly avoided fabricating a prediction but
  padded the gap with ungrounded general clinical reasoning. Needs an explicit
  system-prompt instruction to report tool failures plainly and stop.
- **FAERS OUTC (outcomes) file:** would revive the dropped adverse-event-severity
  model (docs/model_cards.md) with a real serious/fatal outcome label instead of
  the sparse demographic fields currently loaded.
- **Real readmission outcomes:** the readmission model's AUC (~0.51) is
  suppressed by a synthetic, feature-derived proxy label. The architecture
  (Feature Store → MLflow → serving) doesn't change with real outcome data —
  only the label does.
- **Automated eval, not just 10 hand-scored questions:** a small LLM-judge
  harness over a larger question set would catch regressions on every agent
  change instead of relying on a manual re-run.
- **Snowflake reading an external Iceberg table** (docs/iceberg_notes.md flags
  this as time-permitting) — would demonstrate the actual integration point
  between the Phase 3.5 exploration and the production warehouse, not just the
  standalone local demo.

*Built with public data. Architecture mirrors production-grade enterprise patterns.*
