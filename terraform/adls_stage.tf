# Storage integration + external stage that let Snowflake read directly from
# ADLS Gen2 (azure/adf pipeline lands files in raw/, Snowflake COPY INTO reads
# them from here) — see notes/phase3.md and notes/how_it_works.md.
#
# These objects were originally created ad hoc in a Snowflake worksheet on
# 2026-07-06 (confirmed via ACCOUNT_USAGE.QUERY_HISTORY) and were imported
# here (config generated from the live objects via
# `terraform plan -generate-config-out`) so they're managed as code like the
# rest of terraform/ instead of living only as an untracked manual step.

resource "snowflake_storage_integration" "azure_adls" {
  name                      = "AZURE_ADLS_INTEGRATION"
  storage_provider          = "AZURE"
  enabled                   = true
  storage_allowed_locations = ["azure://sthealthpipeline.blob.core.windows.net/raw/"]
  azure_tenant_id           = "0448dae5-261f-4d8b-abbe-0c8d2b6094f1"
}

resource "snowflake_stage" "adls_stage" {
  database            = snowflake_database.raw.name
  schema              = snowflake_schema.raw.name
  name                = "ADLS_STAGE"
  url                 = "azure://sthealthpipeline.blob.core.windows.net/raw/"
  storage_integration = snowflake_storage_integration.azure_adls.name
  comment             = "ADLS Gen2 raw landing zone — ADF drops files here, Snowflake COPY INTO reads them"
}
