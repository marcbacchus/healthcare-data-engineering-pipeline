# Outputs are consumed by other tools later (dbt profiles, ADF connection strings, etc.)

output "warehouse_name" {
  description = "Snowflake virtual warehouse name"
  value       = snowflake_warehouse.compute.name
}

output "raw_database" {
  description = "Raw landing zone database"
  value       = snowflake_database.raw.name
}

output "transform_database" {
  description = "dbt staging + marts database"
  value       = snowflake_database.transform.name
}

output "reporting_database" {
  description = "Analyst-facing reporting database"
  value       = snowflake_database.reporting.name
}

output "loader_role" {
  description = "Role for ingest scripts"
  value       = snowflake_account_role.loader.name
}

output "transformer_role" {
  description = "Role for dbt"
  value       = snowflake_account_role.transformer.name
}

output "reporter_role" {
  description = "Role for BI tools"
  value       = snowflake_account_role.reporter.name
}
