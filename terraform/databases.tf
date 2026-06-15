# Three databases mirror the medallion pattern:
#   RAW       <- untouched source data, written by LOADER
#   TRANSFORM <- dbt staging + marts, written by TRANSFORMER
#   REPORTING <- clean views for BI tools, read by REPORTER
#
# Scaffolding all three now means Phase 2 (dbt) requires zero Terraform changes.

resource "snowflake_database" "raw" {
  name    = "HEALTHCARE_RAW"
  comment = "Landing zone for CMS, FAERS, and Synthea raw data"
}

resource "snowflake_database" "transform" {
  name    = "HEALTHCARE_TRANSFORM"
  comment = "dbt staging models and mart tables"
}

resource "snowflake_database" "reporting" {
  name    = "HEALTHCARE_REPORTING"
  comment = "Analyst-facing views and aggregates"
}

# --- Schemas ---

resource "snowflake_schema" "raw" {
  database = snowflake_database.raw.name
  name     = "RAW"
  comment  = "All raw source tables land here with _loaded_at / _source_file / _row_hash metadata"
}

resource "snowflake_schema" "staging" {
  database = snowflake_database.transform.name
  name     = "STAGING"
  comment  = "dbt staging models — typed, renamed, cast from RAW"
}

resource "snowflake_schema" "marts" {
  database = snowflake_database.transform.name
  name     = "MARTS"
  comment  = "dbt mart models — fct_provider_payments, fct_adverse_events, mart_patient_risk"
}

resource "snowflake_schema" "reporting" {
  database = snowflake_database.reporting.name
  name     = "REPORTING"
  comment  = "Reporter-facing objects, SELECT-only access"
}
