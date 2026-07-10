# Databricks notebook source
# Phase 4 — Feature Engineering: Snowflake → Databricks Feature Store
#
# Reads mart_patient_risk from the governed dbt mart layer in Snowflake,
# engineers 8 features for the readmission risk model, and writes them to
# the Databricks Feature Store (Unity Catalog, primary key: patient_id).
#
# Prerequisites:
#   - Cluster env vars: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD
#   - PyPI library installed on cluster: snowflake-connector-python, databricks-feature-engineering
#   - Role TRANSFORMER has SELECT on HEALTHCARE_TRANSFORM.MARTS.MART_PATIENT_RISK
#   - Unity Catalog workspace — use SHOW CATALOGS to find your catalog name

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Verify Snowflake connection

# COMMAND ----------

import os
import snowflake.connector

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
cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE()")
print(cursor.fetchone())
cursor.close()
conn.close()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Load mart_patient_risk
# MAGIC
# MAGIC We read from the **governed mart layer** (dbt-modeled, tested, typed) rather
# MAGIC than raw source files. Feature inputs are the same data the business uses —
# MAGIC a key guardrail against training/serving skew.

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
cursor.execute("SELECT * FROM MART_PATIENT_RISK")
df_pd = cursor.fetch_pandas_all()
cursor.close()
conn.close()

print(f"Rows loaded: {len(df_pd):,}")
print(f"Columns: {list(df_pd.columns)}")

# COMMAND ----------

df = spark.createDataFrame(df_pd)
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Engineer 8 features
# MAGIC
# MAGIC | # | Feature | Source | Notes |
# MAGIC |---|---------|--------|-------|
# MAGIC | 1 | `age_at_study_end` | mart | numeric |
# MAGIC | 2 | `comorbidity_score` | mart | = active condition count |
# MAGIC | 3 | `total_condition_count` | mart | numeric |
# MAGIC | 4 | `distinct_condition_types` | mart | numeric |
# MAGIC | 5 | `polypharmacy_flag` | mart | boolean → int (0/1) |
# MAGIC | 6 | `income_usd` | mart | numeric |
# MAGIC | 7 | `healthcare_expenses_usd` | mart | numeric |
# MAGIC | 8 | `expense_to_income_ratio` | **derived here** | expenses / (income + 1) |
# MAGIC
# MAGIC `expense_to_income_ratio` is derived in Databricks, not dbt — model-specific
# MAGIC transformations belong in the feature layer, not the business mart layer.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, DoubleType

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
)

print(f"Feature rows: {df_features.count():,}")
print(f"Columns: {df_features.columns}")
display(df_features.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Write to Databricks Feature Store (Unity Catalog)

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient

fe = FeatureEngineeringClient()

# Run SHOW CATALOGS to find your workspace catalog name
CATALOG = "dbw_healthcare_pipeline_7405615280581812"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.healthcare_features")

fe.create_table(
    name=f"{CATALOG}.healthcare_features.patient_risk_features",
    primary_keys=["patient_id"],
    df=df_features,
    description=(
        "8 readmission risk features derived from mart_patient_risk "
        "(dbt-modeled Synthea data). expense_to_income_ratio is the only "
        "feature computed in Databricks; all others sourced from the governed mart layer."
    ),
)

print("Feature table written successfully.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Verify

# COMMAND ----------

df_verify = fe.read_table(name=f"{CATALOG}.healthcare_features.patient_risk_features")
print(f"Feature Store rows: {df_verify.count():,}")
display(df_verify.limit(5))
