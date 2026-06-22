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

*Phase 2 will add: dbt staging → mart layer + GitHub Actions CI/CD*
