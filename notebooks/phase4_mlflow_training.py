# Databricks notebook source
# Phase 4 — MLflow Training: XGBoost Readmission Risk Model
#
# Reads features from the Databricks Feature Store (patient_risk_features),
# creates a synthetic readmission proxy label, trains an XGBoost classifier,
# and logs to MLflow with dual-threshold evaluation (0.35 / 0.50).
#
# Prerequisites:
#   - Cluster libraries: databricks-feature-engineering, xgboost
#   - phase4_feature_engineering.py must have run (Feature Store table must exist)
#   - Cluster env vars: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Imports and MLflow experiment setup

# COMMAND ----------

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup

CATALOG = "dbw_healthcare_pipeline_7405615280581812"

fe = FeatureEngineeringClient()
mlflow.set_experiment("/Users/marc.bacchus@gmail.com/readmission_risk")

print("Setup complete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Load features from Feature Store and create synthetic label
# MAGIC
# MAGIC Synthea does not contain real 30-day readmission events, so we use a
# MAGIC probabilistic proxy label based on comorbidity, age, and financial stress.
# MAGIC This is documented explicitly in the model card — the architecture is
# MAGIC production-ready; the label is a learning stand-in.

# COMMAND ----------

df_features = fe.read_table(
    name=f"{CATALOG}.healthcare_features.patient_risk_features"
).toPandas()

# Synthetic readmission proxy — probability increases with comorbidity, age, financial stress
np.random.seed(42)
prob = (
    0.05
    + 0.08 * (df_features["comorbidity_score"] >= 5).astype(int)
    + 0.05 * (df_features["age_at_study_end"] >= 65).astype(int)
    + 0.04 * (df_features["expense_to_income_ratio"] > 2.0).astype(int)
    + 0.03 * df_features["polypharmacy_flag"]
).clip(0, 1)

df_features["readmitted"] = (np.random.random(len(df_features)) < prob).astype(int)

print(f"Patients: {len(df_features):,}")
print(f"Readmitted (label=1): {df_features['readmitted'].sum()} ({df_features['readmitted'].mean():.1%})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Create Feature Store training set
# MAGIC
# MAGIC `fe.create_training_set()` joins features by primary key at training time.
# MAGIC This ensures the same lookup logic used in training is reused at serving
# MAGIC time — eliminating a common source of training/serving skew.

# COMMAND ----------

df_labels = spark.createDataFrame(df_features[["patient_id", "readmitted"]])

training_set = fe.create_training_set(
    df=df_labels,
    feature_lookups=[
        FeatureLookup(
            table_name=f"{CATALOG}.healthcare_features.patient_risk_features",
            lookup_key="patient_id"
        )
    ],
    label="readmitted",
    exclude_columns=["patient_id"]
)

training_df = training_set.load_df().toPandas()

print(f"Training set rows: {len(training_df):,}")
print(f"Columns: {list(training_df.columns)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Train XGBoost and log to MLflow
# MAGIC
# MAGIC **Dual-threshold rationale:**
# MAGIC - 0.35: high sensitivity — minimise missed high-risk patients. A missed
# MAGIC   readmission (false negative) costs more than an unnecessary intervention.
# MAGIC - 0.50: balanced — standard decision boundary, higher precision.
# MAGIC
# MAGIC Both thresholds are logged so downstream teams can choose based on their
# MAGIC cost tolerance. The model card documents the trade-off explicitly.

# COMMAND ----------

FEATURE_COLS = [
    "age_at_study_end", "comorbidity_score", "total_condition_count",
    "distinct_condition_types", "polypharmacy_flag", "income_usd",
    "healthcare_expenses_usd", "expense_to_income_ratio"
]

X = training_df[FEATURE_COLS]
y = training_df["readmitted"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

with mlflow.start_run(run_name="xgboost_readmission_v1"):

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
        random_state=42,
        eval_metric="auc"
    )
    model.fit(X_train, y_train)

    mlflow.log_params({
        "n_estimators": 100,
        "max_depth": 4,
        "learning_rate": 0.1,
        "test_size": 0.2,
        "label_type": "synthetic_readmission_proxy"
    })

    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    mlflow.log_metric("auc_roc", auc)

    # Threshold 0.35 — high sensitivity
    y_pred_35 = (y_prob >= 0.35).astype(int)
    mlflow.log_metrics({
        "precision_t35": precision_score(y_test, y_pred_35, zero_division=0),
        "recall_t35":    recall_score(y_test, y_pred_35, zero_division=0),
        "f1_t35":        f1_score(y_test, y_pred_35, zero_division=0),
    })

    # Threshold 0.50 — balanced
    y_pred_50 = (y_prob >= 0.50).astype(int)
    mlflow.log_metrics({
        "precision_t50": precision_score(y_test, y_pred_50, zero_division=0),
        "recall_t50":    recall_score(y_test, y_pred_50, zero_division=0),
        "f1_t50":        f1_score(y_test, y_pred_50, zero_division=0),
    })

    fe.log_model(
        model=model,
        artifact_path="readmission_risk_model",
        flavor=mlflow.xgboost,
        training_set=training_set,
        registered_model_name=f"{CATALOG}.healthcare_features.readmission_risk_model"
    )

    print(f"AUC-ROC: {auc:.3f}")
    print(f"\nThreshold 0.35 (high sensitivity):")
    print(f"  Precision: {precision_score(y_test, y_pred_35, zero_division=0):.3f}")
    print(f"  Recall:    {recall_score(y_test, y_pred_35, zero_division=0):.3f}")
    print(f"  F1:        {f1_score(y_test, y_pred_35, zero_division=0):.3f}")
    print(f"\nThreshold 0.50 (balanced):")
    print(f"  Precision: {precision_score(y_test, y_pred_50, zero_division=0):.3f}")
    print(f"  Recall:    {recall_score(y_test, y_pred_50, zero_division=0):.3f}")
    print(f"  F1:        {f1_score(y_test, y_pred_50, zero_division=0):.3f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Verify MLflow run

# COMMAND ----------

client = mlflow.tracking.MlflowClient()
experiment = client.get_experiment_by_name("/Users/marc.bacchus@gmail.com/readmission_risk")
runs = client.search_runs(experiment.experiment_id)
print(f"Runs logged: {len(runs)}")
print(f"Latest run AUC: {runs[0].data.metrics['auc_roc']:.3f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Results summary
# MAGIC
# MAGIC AUC ~0.51 is expected — the synthetic label is probabilistic with significant
# MAGIC noise, and the small dataset (1,161 patients) limits signal. The architecture
# MAGIC (Feature Store lookup → XGBoost → MLflow dual-threshold logging) is
# MAGIC production-ready. With real 30-day readmission labels, AUC would be
# MAGIC meaningfully higher.
# MAGIC
# MAGIC **Next:** Phase 4 Step 3 — train models 2 and 3 (adverse event severity +
# MAGIC provider payment anomaly), then deploy the readmission model to
# MAGIC Databricks Model Serving.
