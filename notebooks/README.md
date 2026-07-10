# Phase 4 — Databricks + MLflow: Notebooks

Databricks notebooks for Phase 4 — feature engineering, model training, and model
serving. Stored as Python source files (Databricks notebook format with
`# COMMAND ----------` cell separators) so they can be version-controlled and
imported directly into any Databricks workspace.

---

## What Was Built

### Feature Engineering
- Connected Databricks to Snowflake using the TRANSFORMER role (least privilege)
- Read `mart_patient_risk` from the governed dbt mart layer — same data the business uses, eliminating training/serving skew at the source
- Engineered 8 features; 7 passed through from the dbt mart, 1 (`expense_to_income_ratio`) derived in Databricks as a model-specific transformation
- Registered feature table in Databricks Feature Store (Unity Catalog) with `patient_id` as primary key

### Models

**Readmission Risk (XGBoost)**
- Training set built via `fe.create_training_set()` + `FeatureLookup` — Feature Store pattern, not a raw table read
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

---

## Notebooks

| Notebook | Purpose |
|----------|---------|
| `phase4_feature_engineering.py` | Reads `mart_patient_risk` from Snowflake, engineers 8 features, writes to Databricks Feature Store (Unity Catalog) |
| `phase4_mlflow_training.py` | Builds Feature Store training set, trains XGBoost readmission risk model, logs to MLflow with dual-threshold evaluation |
| `phase4_models_2_3.py` | IsolationForest payment anomaly detection on 100K CMS records; documents dropped adverse event severity model |
| `phase4_model_serving.py` | Re-logs model with explicit signature for serving, tests live Databricks Model Serving REST endpoint |

---

## Prerequisites

**Cluster setup (Databricks):**
- Runtime: 17.3 LTS (Spark 3.5, Scala 2.12), Hybrid compute mode
- Libraries (install via Cluster → Libraries → PyPI):
  - `snowflake-connector-python`
  - `databricks-feature-engineering`
  - `xgboost`
- Environment variables (Cluster → Edit → Advanced Options → Environment Variables):
  - `SNOWFLAKE_ACCOUNT` — format: `orgname-accountname`
  - `SNOWFLAKE_USER`
  - `SNOWFLAKE_PASSWORD`

**Run order:** notebooks are designed to run sequentially —
`feature_engineering` → `mlflow_training` → `models_2_3` → `model_serving`

**Note:** Library installs do not persist across cluster restarts. Reinstall
after each restart, then run `dbutils.library.restartPython()` before executing
notebook cells.

---

## Key Design Decisions

**Why read from the dbt mart layer, not raw tables?**
Feature inputs are the same governed, tested data the business uses. This
eliminates training/serving skew at the source — a key guardrail in production ML.

**Why is `expense_to_income_ratio` derived in Databricks, not dbt?**
It is a model-specific transformation. Business marts should reflect business
concepts; model-specific feature transformations belong in the feature layer.

**Why dual thresholds (0.35 and 0.50)?**
A missed high-risk patient (false negative) costs more than an unnecessary
intervention (false positive) in a readmission context. Both thresholds are
logged so downstream teams can choose based on their cost tolerance and
intervention capacity.

**Why was the adverse event severity model dropped?**
FAERS demographic fields were entirely null in the loaded dataset. Rather than
engineer around bad data, the model was dropped and the decision documented.
Path to revival: load the FAERS OUTC (outcomes) file, which contains
serious/fatal outcome flags.

---

## Model Cards

Full model documentation — intended use, metrics, threshold rationale,
limitations, and bias considerations — in [docs/model_cards.md](../docs/model_cards.md).
