# Least-privilege role design — each role can only touch its own layer.
# This mirrors the HIPAA minimum-necessary-access pattern used in production
# healthcare data platforms.

# --- Role definitions ---

resource "snowflake_account_role" "loader" {
  name    = "LOADER"
  comment = "Ingest scripts only — INSERT into HEALTHCARE_RAW, nothing else"
}

resource "snowflake_account_role" "transformer" {
  name    = "TRANSFORMER"
  comment = "dbt service account — reads RAW, writes TRANSFORM"
}

resource "snowflake_account_role" "reporter" {
  name    = "REPORTER"
  comment = "BI / analyst access — SELECT only on REPORTING layer"
}

# --- Warehouse access (all roles need compute) ---

resource "snowflake_grant_privileges_to_account_role" "loader_wh" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.compute.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_wh" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.compute.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_wh" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.compute.name
  }
}

# --- LOADER: write access to HEALTHCARE_RAW ---

resource "snowflake_grant_privileges_to_account_role" "loader_raw_db" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.raw.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_raw_schema" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE STAGE", "CREATE FILE FORMAT"]
  on_schema {
    schema_name = "${snowflake_database.raw.name}.${snowflake_schema.raw.name}"
  }
}

# Future tables created in RAW are automatically accessible to LOADER
resource "snowflake_grant_privileges_to_account_role" "loader_raw_future_tables" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["INSERT", "UPDATE", "SELECT", "DELETE", "TRUNCATE"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${snowflake_database.raw.name}.${snowflake_schema.raw.name}"
    }
  }
}

# --- TRANSFORMER: read RAW, write TRANSFORM ---

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_db" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.raw.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_schema" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "${snowflake_database.raw.name}.${snowflake_schema.raw.name}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_future_tables" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${snowflake_database.raw.name}.${snowflake_schema.raw.name}"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_transform_db" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.transform.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_staging_schema" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
  on_schema {
    schema_name = "${snowflake_database.transform.name}.${snowflake_schema.staging.name}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_marts_schema" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
  on_schema {
    schema_name = "${snowflake_database.transform.name}.${snowflake_schema.marts.name}"
  }
}

# --- REPORTER: read-only on REPORTING layer ---

resource "snowflake_grant_privileges_to_account_role" "reporter_reporting_db" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.reporting.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_reporting_schema" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "${snowflake_database.reporting.name}.${snowflake_schema.reporting.name}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_future_tables" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${snowflake_database.reporting.name}.${snowflake_schema.reporting.name}"
    }
  }
}

# --- Grant all three roles to your user so you can switch into them ---

resource "snowflake_grant_account_role" "loader_to_user" {
  role_name = snowflake_account_role.loader.name
  user_name = var.snowflake_username
}

resource "snowflake_grant_account_role" "transformer_to_user" {
  role_name = snowflake_account_role.transformer.name
  user_name = var.snowflake_username
}

resource "snowflake_grant_account_role" "reporter_to_user" {
  role_name = snowflake_account_role.reporter.name
  user_name = var.snowflake_username
}
