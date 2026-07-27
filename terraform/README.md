# Phase 1 — Terraform: Snowflake Infrastructure as Code

All Snowflake objects are provisioned via Terraform — no manual UI clicks.
The full environment can be torn down and rebuilt reproducibly from this directory.

## What's provisioned

| Resource | Name | Notes |
|---|---|---|
| Database | `HEALTHCARE_RAW` | Raw landing zone — all source data loads here |
| Database | `HEALTHCARE_TRANSFORM` | dbt staging and mart models (Phase 2) |
| Database | `HEALTHCARE_REPORTING` | Reserved for BI / reporting layer (Phase 5) |
| Schema | `RAW` | Inside `HEALTHCARE_RAW` |
| Schema | `STAGING` | Inside `HEALTHCARE_TRANSFORM` |
| Schema | `MARTS` | Inside `HEALTHCARE_TRANSFORM` |
| Schema | `REPORTING` | Inside `HEALTHCARE_REPORTING` |
| Warehouse | `COMPUTE_WH` | X-SMALL, auto-suspend 60s, auto-resume |
| Role | `LOADER` | Writes raw data into `HEALTHCARE_RAW` |
| Role | `TRANSFORMER` | Reads RAW, writes STAGING/MARTS |
| Role | `REPORTER` | SELECT-only on marts |
| Storage integration | `AZURE_ADLS_INTEGRATION` | Lets Snowflake read directly from ADLS Gen2 (Phase 3) |
| Stage | `ADLS_STAGE` | External stage in `HEALTHCARE_RAW.RAW`, source for the ADF/Airflow `COPY INTO` pipelines |

## Role hierarchy

```
ACCOUNTADMIN
  └── SYSADMIN
        ├── LOADER      → WRITE to HEALTHCARE_RAW.RAW
        ├── TRANSFORMER → READ from HEALTHCARE_RAW, WRITE to HEALTHCARE_TRANSFORM
        └── REPORTER    → SELECT on HEALTHCARE_TRANSFORM.MARTS
```

This enforces a one-way data flow at the permission level. dbt (TRANSFORMER) cannot
modify raw data. BI tools (REPORTER) cannot break anything upstream. Schema drift or
a runaway dbt model cannot corrupt the source of truth.

## Usage

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# fill in: snowflake_account, snowflake_user, snowflake_password

terraform init
terraform plan
terraform apply
```

## Files

| File | Purpose |
|---|---|
| `main.tf` | Provider config, Terraform version constraints |
| `variables.tf` | Input variable declarations |
| `terraform.tfvars.example` | Template — copy to `terraform.tfvars` and fill in credentials |
| `databases.tf` | Database and schema definitions |
| `warehouses.tf` | Warehouse config (size, auto-suspend, auto-resume) |
| `roles.tf` | Roles, grants, and role hierarchy |
| `adls_stage.tf` | Azure storage integration + external stage (imported, see note below) |
| `outputs.tf` | Output values (account locator, warehouse name) |

## Note: importing pre-existing objects

`adls_stage.tf` was not created by `terraform apply` from scratch — the
`AZURE_ADLS_INTEGRATION` storage integration and `ADLS_STAGE` external stage
were originally run ad hoc in a Snowflake worksheet during Phase 3 (2026-07-06),
before this project's "everything as code" rule was applied consistently.

When that gap was noticed, the objects were reconciled into Terraform state
rather than recreated:

1. Confirmed the objects were real and found who/when created them via
   `SELECT query_text, user_name, start_time FROM snowflake.account_usage.query_history WHERE query_text ILIKE '%ADLS_STAGE%'`
2. Added `import` blocks targeting the resource addresses + Snowflake object IDs
   (`AZURE_ADLS_INTEGRATION` for the integration; `HEALTHCARE_RAW|RAW|ADLS_STAGE`
   pipe-delimited for the stage)
3. Ran `terraform plan -generate-config-out=<file>.tf` to generate HCL from the
   *live* object properties instead of hand-typing config and risking drift
4. Reviewed/trimmed the generated config, ran `terraform apply` to complete
   the import, then deleted the now-consumed `import` blocks

If you ever find another object that exists in Snowflake but not in this
directory, this is the playbook — `account_usage.query_history` first (to
confirm it's real and see its origin), then `plan -generate-config-out`
before hand-writing anything.
