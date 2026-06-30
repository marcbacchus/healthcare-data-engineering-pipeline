# Architecture

This diagram is updated at the end of each phase to show the cumulative state of the platform.

---

## Phase 1 — Snowflake Foundation + Raw Ingest

```mermaid
flowchart LR
    subgraph sources["Data Sources"]
        cms["CMS Open Payments\nDKAN API"]
        faers["FDA FAERS\nopenFDA REST API"]
        synthea["Synthea\nlocal generation"]
    end

    subgraph ingest["Python Ingest  ·  ingest/"]
        scripts["load_cms.py\nload_faers.py\nload_synthea.py"]
        utils["snowflake_utils.py\nconnect · add_metadata · load"]
    end

    subgraph sf["Snowflake — HEALTHCARE_RAW.RAW"]
        direction TB
        t1["CMS_OPEN_PAYMENTS\n100K rows"]
        t2["FAERS_DEMO\n26K rows"]
        t3["SYNTHEA_PATIENTS\n1,161 rows"]
        t4["SYNTHEA_CONDITIONS\n42,639 rows"]
    end

    subgraph iac["Infrastructure as Code  ·  terraform/"]
        tf["Terraform\ndatabases · warehouse\nroles: LOADER / TRANSFORMER / REPORTER"]
    end

    cms     --> scripts
    faers   --> scripts
    synthea --> scripts
    scripts --> utils
    utils   --> t1 & t2 & t3 & t4
    tf      -. "provisions" .-> sf
```

**Roles provisioned by Terraform:**

| Role | Permissions |
|---|---|
| `LOADER` | Write to `HEALTHCARE_RAW` |
| `TRANSFORMER` | Read RAW, write `HEALTHCARE_TRANSFORM` |
| `REPORTER` | SELECT-only on marts |

All ingest runs are **idempotent** — each script truncates before loading so re-runs produce the same table state.

---

---

## Phase 2 — dbt Transformations + CI/CD

```mermaid
flowchart LR
    subgraph sources["Data Sources"]
        cms["CMS Open Payments"]
        faers["FDA FAERS"]
        synthea["Synthea"]
    end

    subgraph raw["Snowflake — HEALTHCARE_RAW.RAW  ·  Phase 1"]
        t1["CMS_OPEN_PAYMENTS"]
        t2["FAERS_DEMO"]
        t3["SYNTHEA_PATIENTS"]
        t4["SYNTHEA_CONDITIONS"]
    end

    subgraph dbt_stg["dbt Staging  ·  HEALTHCARE_TRANSFORM.STAGING"]
        s1["stg_cms_open_payments\n(view)"]
        s2["stg_faers_demo\n(view)"]
        s3["stg_synthea_patients\n(view)"]
        s4["stg_synthea_conditions\n(view)"]
    end

    subgraph dbt_mart["dbt Marts  ·  HEALTHCARE_TRANSFORM.MARTS"]
        m1["fct_provider_payments\n(table)"]
        m2["fct_adverse_events\n(table)"]
        m3["mart_patient_risk\n(table)"]
    end

    subgraph cicd["CI/CD  ·  .github/workflows/"]
        gh["GitHub Actions\ndbt test on every PR\ndbt docs → GitHub Pages"]
    end

    sources --> raw
    t1 --> s1
    t2 --> s2
    t3 & t4 --> s3 & s4
    s1 --> m1
    s2 --> m2
    s3 & s4 --> m3
    dbt_stg & dbt_mart -. "22 tests" .-> gh
```

**dbt model summary:**

| Layer | Models | Materialization | Tests |
|---|---|---|---|
| Staging | 4 | View | 6 (not_null, unique, relationships) |
| Marts | 3 | Table | 16 (not_null, unique, accepted_values) |

**Key mart features for downstream phases:**

- `mart_patient_risk.risk_tier` — high/medium/low stratification, drives Phase 4 ML cohort selection
- `mart_patient_risk.comorbidity_score` — active condition count, seed feature for Phase 4 Feature Store
- `mart_patient_risk.polypharmacy_flag` — proxy flag (≥5 active conditions); replaced with medication count in Phase 4
