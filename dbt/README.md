# Phase 2 — dbt: Staging Models, Mart Transforms, CI/CD

dbt Core project wired to Snowflake via the `TRANSFORMER` role.
Transforms raw VARCHAR data from `HEALTHCARE_RAW.RAW` into typed,
tested analytics tables in `HEALTHCARE_TRANSFORM`.

## Layer map

```
HEALTHCARE_RAW.RAW (Phase 1)
  └── HEALTHCARE_TRANSFORM.STAGING  ← 4 staging views
        └── HEALTHCARE_TRANSFORM.MARTS   ← 3 mart tables
```

## Models

| Layer | Model | Grain | Rows |
|---|---|---|---|
| Staging | `stg_cms_open_payments` | 1 per payment record | ~100K |
| Staging | `stg_faers_demo` | 1 per FAERS report | ~26K |
| Staging | `stg_synthea_patients` | 1 per patient | 1,161 |
| Staging | `stg_synthea_conditions` | 1 per diagnosis episode | varies |
| Mart | `fct_provider_payments` | 1 per CMS payment | ~100K |
| Mart | `fct_adverse_events` | 1 per FAERS report | ~26K |
| Mart | `mart_patient_risk` | 1 per patient | 1,161 |

## Tests

22 data tests across all models (`not_null`, `unique`, `accepted_values`, `relationships`).
All tests pass against Snowflake. CI enforces tests on every PR.

## Local development

Credentials come from `ingest/.env` (gitignored). Run from this directory:

```bash
# load creds into shell
set -a && source ../ingest/.env && set +a

dbt debug --profiles-dir .    # verify connection
dbt run   --profiles-dir .    # build all models
dbt test  --profiles-dir .    # run all tests
dbt docs generate --profiles-dir . && dbt docs serve   # browse lineage
```

## CI/CD

`.github/workflows/dbt_ci.yml` runs `dbt run + dbt test` on every PR
that touches `dbt/**`. Snowflake credentials are stored as GitHub Secrets
(`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`).
