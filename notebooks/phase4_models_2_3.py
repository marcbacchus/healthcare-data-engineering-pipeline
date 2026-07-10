# Databricks notebook source
# Phase 4 — Models 2 & 3: Adverse Event Severity + Provider Payment Anomaly
#
# Model 2 (Adverse Event Severity / Random Forest): DROPPED
#   FAERS demographic data too sparse — AGE_GROUP uniform, INITIAL_OR_FOLLOWUP
#   entirely null. Deferred pending richer outcome data. This is the prescribed
#   trim per roadmap: "drop adverse event severity before cutting anything else."
#
# Model 3 (Provider Payment Anomaly / IsolationForest): COMPLETE
#   Reads fct_provider_payments (100K CMS records), detects anomalous payment
#   patterns using unsupervised IsolationForest. Logged to MLflow with signature.
#
# Prerequisites:
#   - Cluster libraries: databricks-feature-engineering (for CATALOG var reuse)
#   - Cluster env vars: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD

# COMMAND ----------

# MAGIC %md
# MAGIC ## Imports

# COMMAND ----------

import os
import mlflow
import mlflow.sklearn
import snowflake.connector
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from mlflow.models.signature import infer_signature

CATALOG = "dbw_healthcare_pipeline_7405615280581812"

print("Imports complete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Model 2 — Adverse Event Severity (DROPPED)
# MAGIC
# MAGIC FAERS demographic data was too sparse for classification:
# MAGIC - `PATIENT_AGE_YEARS` and `IS_INITIAL_REPORT`: 26,000/26,000 null
# MAGIC - `AGE_GROUP`: uniform (all same value after staging)
# MAGIC - `INITIAL_OR_FOLLOWUP`: entirely null
# MAGIC
# MAGIC Deferred pending richer FAERS outcome data (OUTC file would add serious/fatal
# MAGIC outcome flags). Roadmap explicitly allows this trim before cutting other phases.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Model 3 — Provider Payment Anomaly (IsolationForest)
# MAGIC
# MAGIC Unsupervised anomaly detection on CMS Open Payments data. No label needed —
# MAGIC IsolationForest flags statistically unusual payment patterns by isolating
# MAGIC observations that are easy to separate from the rest of the distribution.
# MAGIC
# MAGIC **Features:** payment_amount_usd, payment_count, payment_quarter, is_foreign_recipient
# MAGIC **Contamination:** 0.05 (assume ~5% of payments are anomalous)

# COMMAND ----------

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    role="TRANSFORMER",
    warehouse="COMPUTE_WH",
    database="HEALTHCARE_TRANSFORM",
    schema="MARTS"
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM FCT_PROVIDER_PAYMENTS")
df_cms = cursor.fetch_pandas_all()
cursor.close()
conn.close()

print(f"Rows loaded: {len(df_cms):,}")
print(df_cms[["PAYMENT_AMOUNT_USD", "PAYMENT_COUNT", "PAYMENT_QUARTER", "IS_FOREIGN_RECIPIENT"]].isnull().sum())

# COMMAND ----------

mlflow.set_experiment("/Users/marc.bacchus@gmail.com/provider_payment_anomaly")

features = ["PAYMENT_AMOUNT_USD", "PAYMENT_COUNT", "PAYMENT_QUARTER", "IS_FOREIGN_RECIPIENT"]
X_cms = df_cms[features].astype(float)

with mlflow.start_run(run_name="isolation_forest_payment_anomaly_v1"):

    model_if = IsolationForest(
        n_estimators=100,
        contamination=0.05,
        random_state=42
    )
    model_if.fit(X_cms)

    df_cms["anomaly_flag"] = (model_if.predict(X_cms) == -1).astype(int)
    df_cms["anomaly_score"] = model_if.decision_function(X_cms)

    mlflow.log_params({
        "n_estimators": 100,
        "contamination": 0.05,
        "features": str(features),
        "model_type": "unsupervised_anomaly_detection"
    })
    mlflow.log_metrics({
        "anomalies_detected": int(df_cms["anomaly_flag"].sum()),
        "anomaly_rate": float(df_cms["anomaly_flag"].mean()),
        "mean_anomaly_score": float(df_cms["anomaly_score"].mean()),
        "min_anomaly_score": float(df_cms["anomaly_score"].min()),
    })

    signature = infer_signature(X_cms, model_if.predict(X_cms))

    mlflow.sklearn.log_model(
        model_if,
        name="payment_anomaly_model",
        signature=signature,
        input_example=X_cms.iloc[:5],
        registered_model_name=f"{CATALOG}.healthcare_features.payment_anomaly_model"
    )

    print(f"Anomalies detected: {df_cms['anomaly_flag'].sum():,} ({df_cms['anomaly_flag'].mean():.1%})")
    print(f"Mean anomaly score: {df_cms['anomaly_score'].mean():.4f}")
    print(f"\nTop 5 anomalous payments:")
    display(df_cms.nsmallest(5, "anomaly_score")[
        ["PAYMENT_AMOUNT_USD", "PAYMENT_COUNT", "PAYMENT_QUARTER", "IS_FOREIGN_RECIPIENT", "anomaly_score"]
    ])
