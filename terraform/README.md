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
| `outputs.tf` | Output values (account locator, warehouse name) |
