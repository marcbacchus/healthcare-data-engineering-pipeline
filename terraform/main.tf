terraform {
  required_version = ">= 1.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 0.100"
    }
  }
}

# ACCOUNTADMIN is used only for provisioning infra objects.
# Day-to-day work (ingest, dbt, BI) uses LOADER / TRANSFORMER / REPORTER.
provider "snowflake" {
  organization_name = var.snowflake_org
  account_name      = var.snowflake_account
  user              = var.snowflake_username
  password          = var.snowflake_password
  role              = "ACCOUNTADMIN"
}
