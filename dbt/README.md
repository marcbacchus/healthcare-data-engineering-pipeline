# Phase 2 — dbt: Staging through Marts + CI/CD

dbt Core project wired to Snowflake via the `TRANSFORMER` role.
Transforms raw VARCHAR data from `HEALTHCARE_RAW.RAW` into typed,
tested analytics tables in `HEALTHCARE_TRANSFORM`.

## Layer map

```
HEALTHCARE_RAW.RAW  (Phase 1 — VARCHAR everything)
  └── HEALTHCARE_TRANSFORM.STAGING   ← 4 staging views (typed, renamed, cleaned)
        └── HEALTHCARE_TRANSFORM.MARTS    ← 3 mart tables (business logic, joins)
```

Staging = make it trustworthy. Marts = make it useful.

## Staging models

Materialized as **views** — no storage cost, always reflect the latest raw data.
Every model applies `NULLIF(..., '')` to convert empty strings to NULL, and uses
`TRY_TO_DATE` / `TRY_TO_NUMBER` so type errors surface as NULLs rather than
pipeline failures.

| Model | Source | Key transforms |
|---|---|---|
| `stg_cms_open_payments` | `CMS_OPEN_PAYMENTS` | Renames 61-char CMS column names, casts payment amount via `TRY_TO_NUMBER`, date via `TRY_TO_DATE('MM/DD/YYYY')` |
| `stg_faers_demo` | `FAERS_DEMO` | Normalizes patient age across 5 reporting units (YR/DEC/MON/WK/DY) into a single `patient_age_years` field; casts dates via `TRY_TO_DATE('YYYYMMDD')` |
| `stg_synthea_patients` | `SYNTHEA_PATIENTS` | Casts dates and numeric socioeconomic fields |
| `stg_synthea_conditions` | `SYNTHEA_CONDITIONS` | Derives `is_active` flag (`stop_date IS NULL`), preserves SNOMED-CT codes |

## Mart models

Materialized as **tables** — pre-computed for query performance. Grain documented on each.

| Model | Grain | Rows | Key additions |
|---|---|---|---|
| `fct_provider_payments` | 1 per CMS payment | ~100K | `is_foreign_recipient`, `payment_year`, `payment_quarter`; filtered to non-null amount + date |
| `fct_adverse_events` | 1 per FAERS report | ~26K | `is_initial_report`, `report_year`, `report_quarter` |
| `mart_patient_risk` | 1 per patient | 1,161 | `comorbidity_score`, `polypharmacy_flag` (≥5 active conditions), `risk_tier` (high/medium/low) — feeds Phase 4 Feature Store |

## Tests

22 data tests across all models, enforced by CI on every PR:

| Test type | Count | Applied to |
|---|---|---|
| `not_null` | 12 | Key columns on all staging + mart models |
| `unique` | 7 | Primary keys on all staging + mart models |
| `accepted_values` | 2 | `initial_or_followup` (I/F), `risk_tier` (high/medium/low) |
| `relationships` | 1 | `stg_synthea_conditions.patient_id` → `stg_synthea_patients.patient_id` |

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `dbt_ci.yml` | Every PR touching `dbt/**` | Runs `dbt run` + `dbt test` against Snowflake; PR fails if any test breaks |
| `dbt_docs.yml` | Merge to `main` | Generates and deploys dbt docs to GitHub Pages |

## Local development

```bash
# from project root
source .env

cd dbt/
dbt debug --profiles-dir .                                    # verify connection
dbt run   --profiles-dir .                                    # build all models
dbt test  --profiles-dir .                                    # run all 22 tests
dbt docs generate --profiles-dir . && dbt docs serve          # browse lineage locally
```

Credentials are read from `.env` at the project root (gitignored).
See `.env.example` for required variables.
