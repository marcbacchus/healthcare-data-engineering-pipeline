# Docs

Project documentation — architecture diagrams, data dictionary, exploration notes,
and model cards. Updated at the end of each phase.

---

## Contents

| File | Phase | Purpose |
|------|-------|---------|
| `architecture.md` | All | Cumulative architecture diagrams (Mermaid) — updated each phase to show the growing platform |
| `data_dictionary.md` | 1–2 | Column-level definitions for all raw and mart tables; data types, nullability, business meaning |
| `iceberg_notes.md` | 3.5 | Apache Iceberg exploration — what it solves vs. plain Parquet/Hive, schema evolution, time travel demo, honest POV on when to reach for it |
| `model_cards.md` | 4 | Model documentation for all Phase 4 models — intended use, features, metrics, threshold rationale, limitations, bias considerations |

---

## Model Cards Summary

Two models trained in Phase 4:

- **Readmission Risk (XGBoost)** — live REST endpoint on Databricks Model Serving. Dual-threshold logging (0.35 / 0.50). Synthetic proxy label; AUC reflects label noise, not architecture limitations.
- **Provider Payment Anomaly (IsolationForest)** — batch anomaly detection on 100K CMS payments. 4,994 flagged at 5% contamination. Not deployed to a live endpoint (batch workload).
- **Adverse Event Severity (Random Forest)** — dropped; FAERS demographic data too sparse. Path to revival documented.

Full detail: [model_cards.md](model_cards.md)

---

## Architecture Diagrams

`architecture.md` contains cumulative Mermaid diagrams — one per phase, each
building on the last. Phases covered:

- Phase 1: Snowflake foundation + raw ingest
- Phase 2: dbt transformation layer + CI/CD
- Phase 3: Azure orchestration (ADF + ADLS + Key Vault + Snowpipe)
- Phase 4: Databricks + MLflow + Model Serving *(diagram pending)*
