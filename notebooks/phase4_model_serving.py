# Databricks notebook source
# Phase 4 — Model Serving: Readmission Risk Live Endpoint
#
# Logs the XGBoost readmission risk model with MLflow signature (no Feature Store
# dependency) and tests the live Databricks Model Serving endpoint.
#
# Endpoint: readmission_risk_model (serverless, scale-to-zero)
# Workspace: adb-7405615280581812.12.azuredatabricks.net
#
# Prerequisites:
#   - phase4_mlflow_training.py cells re-run to get model + X_test in scope
#   - Cluster libraries: databricks-feature-engineering, xgboost

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Re-log model without Feature Store dependency
# MAGIC
# MAGIC The original model was logged via `fe.log_model()` which requires an online
# MAGIC Feature Store for serving. For a direct REST endpoint, we re-log using
# MAGIC `mlflow.xgboost.log_model()` with an explicit signature — the endpoint then
# MAGIC accepts raw feature values directly.

# COMMAND ----------

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import os
import snowflake.connector
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from mlflow.models.signature import infer_signature
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, DoubleType

CATALOG = "dbw_healthcare_pipeline_7405615280581812"
fe = FeatureEngineeringClient()
mlflow.set_experiment("/Users/marc.bacchus@gmail.com/readmission_risk")

# COMMAND ----------

# Reload data from Snowflake
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
cursor.execute("SELECT * FROM MART_PATIENT_RISK")
df_pd = cursor.fetch_pandas_all()
cursor.close()
conn.close()

df = spark.createDataFrame(df_pd)

df_features = (
    df
    .select(
        "patient_id",
        F.col("age_at_study_end").cast(IntegerType()),
        F.col("comorbidity_score").cast(IntegerType()),
        F.col("total_condition_count").cast(IntegerType()),
        F.col("distinct_condition_types").cast(IntegerType()),
        F.col("polypharmacy_flag").cast(IntegerType()),
        F.col("income_usd").cast(DoubleType()),
        F.col("healthcare_expenses_usd").cast(DoubleType()),
    )
    .withColumn(
        "expense_to_income_ratio",
        (F.col("healthcare_expenses_usd") / (F.col("income_usd") + F.lit(1.0))).cast(DoubleType())
    )
    .filter(F.col("patient_id").isNotNull())
).toPandas()

np.random.seed(42)
prob = (
    0.05
    + 0.08 * (df_features["comorbidity_score"] >= 5).astype(int)
    + 0.05 * (df_features["age_at_study_end"] >= 65).astype(int)
    + 0.04 * (df_features["expense_to_income_ratio"] > 2.0).astype(int)
    + 0.03 * df_features["polypharmacy_flag"]
).clip(0, 1)
df_features["readmitted"] = (np.random.random(len(df_features)) < prob).astype(int)

FEATURE_COLS = [
    "age_at_study_end", "comorbidity_score", "total_condition_count",
    "distinct_condition_types", "polypharmacy_flag", "income_usd",
    "healthcare_expenses_usd", "expense_to_income_ratio"
]

X = df_features[FEATURE_COLS]
y = df_features["readmitted"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = XGBClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.1,
    scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
    random_state=42, eval_metric="auc"
)
model.fit(X_train, y_train)
print("Model trained.")

# COMMAND ----------

with mlflow.start_run(run_name="xgboost_readmission_v2_serving"):

    signature = infer_signature(X_test, model.predict_proba(X_test)[:, 1])

    mlflow.xgboost.log_model(
        model,
        name="readmission_risk_model_serving",
        signature=signature,
        input_example=X_test.iloc[:5],
        registered_model_name=f"{CATALOG}.healthcare_features.readmission_risk_model_serving"
    )

    print("Model registered for serving.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Test the live endpoint
# MAGIC
# MAGIC Test patient: age 72, 6 active conditions, $85K expenses on $35K income.
# MAGIC Expected: prediction = 1 (high readmission risk).

# COMMAND ----------

import requests

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
workspace_url = "https://adb-7405615280581812.12.azuredatabricks.net"
endpoint_url = f"{workspace_url}/serving-endpoints/readmission_risk_model/invocations"

test_payload = {
    "dataframe_records": [
        {
            "age_at_study_end": 72,
            "comorbidity_score": 6,
            "total_condition_count": 12,
            "distinct_condition_types": 8,
            "polypharmacy_flag": 1,
            "income_usd": 35000.0,
            "healthcare_expenses_usd": 85000.0,
            "expense_to_income_ratio": 2.43
        }
    ]
}

response = requests.post(
    endpoint_url,
    headers={"Authorization": f"Bearer {token}"},
    json=test_payload
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
# Expected: {'predictions': [1]}
