# Phase 3 — Azure Orchestration: ADF, ADLS Gen2, Key Vault, Snowpipe

Production ingestion pipeline: HTTP source → ADLS Gen2 → Snowflake external
stage → COPY INTO, orchestrated by Azure Data Factory with Key Vault-managed
credentials and Azure Monitor alerting.

---

## Azure Resources

All resources in resource group `rg-healthcare-pipeline` (East US), tagged:
`project=healthcare-pipeline`, `phase=3`, `env=dev`, `owner=marc-bacchus`.

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `rg-healthcare-pipeline` | Logical container for all Phase 3 infra |
| ADLS Gen2 | `sthealthpipeline` | Raw landing zone — files land here before Snowflake load |
| Key Vault | `kv-health-pipeline` | Snowflake credentials as secrets, RBAC-based managed identity access |
| Data Factory | `adf-healthcare-pipeline` | *(Week 7)* Orchestrates HTTP → ADLS → Snowflake pipeline |

## Design Decisions

**Why ADLS Gen2 (not plain Blob Storage)?**
Hierarchical namespace enables directory-level ACLs and is required for
Snowflake external stages and ADF integration patterns used in production
healthcare data platforms.

**Why Key Vault with RBAC (not access policies)?**
RBAC-based Key Vault is the modern Azure pattern — no per-secret ACL
management, integrates cleanly with managed identities, and aligns with
least-privilege grant at the resource level.

**Why managed identity (not service principal + secret)?**
Service principal secrets expire and require rotation. Managed identity
is credential-free — ADF authenticates to Key Vault automatically. No
secrets in config files, no rotation incidents.

## Setup

Resources are provisioned via `az` CLI. ARM template export for full
reproducibility: [`arm/`](arm/) *(added at Week 8 completion)*.

```bash
az login
az account set --subscription <subscription-id>

# Resource group
az group create --name rg-healthcare-pipeline --location eastus \
  --tags project=healthcare-pipeline phase=3 env=dev owner=marc-bacchus

# ADLS Gen2
az storage account create --name sthealthpipeline \
  --resource-group rg-healthcare-pipeline --location eastus \
  --sku Standard_LRS --kind StorageV2 --enable-hierarchical-namespace true

az storage fs create --name raw --account-name sthealthpipeline --auth-mode login

# Key Vault
az keyvault create --name kv-health-pipeline \
  --resource-group rg-healthcare-pipeline --location eastus \
  --enable-rbac-authorization true

# Store Snowflake credentials (values from .env)
az keyvault secret set --vault-name kv-health-pipeline --name snowflake-account  --value <value>
az keyvault secret set --vault-name kv-health-pipeline --name snowflake-user     --value <value>
az keyvault secret set --vault-name kv-health-pipeline --name snowflake-password --value <value>
```

## ADF vs Airflow — Orchestration Tradeoffs

Both pipelines run the same logical steps: resolve CMS URL → copy sources to
ADLS → Snowflake COPY INTO. The implementation differences reveal when to reach
for each tool.

| Dimension | ADF | Airflow (local Docker) |
|---|---|---|
| **Setup** | Managed service — no infra to run | Self-hosted: you run scheduler, workers, metadata DB |
| **Authoring** | GUI + JSON export | Python code (DAG-as-code), version-controlled natively |
| **Auth to Azure** | Managed identity — zero secrets | Account key or service principal in config |
| **Dynamic logic** | Web activity + expressions (limited) | Full Python — any logic, any library |
| **Ops burden** | Zero — Microsoft runs it | You own uptime, upgrades, scaling |
| **Cost model** | Pay per activity run | Fixed infra cost (or k8s overhead) |
| **Observability** | Azure Monitor, built-in pipeline runs UI | Airflow UI + your own alerting stack |
| **Portability** | Azure-only | Runs anywhere Docker runs |
| **Best for** | Azure-native orgs, non-engineer pipeline builders, compliance-heavy environments where managed services reduce attack surface | Code-first data teams, complex DAG logic, multi-cloud, teams that want full control over the scheduler |

**When to reach for ADF:** Your org is Azure-committed, the pipeline is
straightforward (copy + transform), and you want managed auth, built-in
monitoring, and zero scheduler ops. Common in regulated healthcare/finance.

**When to reach for Airflow:** Your team writes Python, the DAG logic is
complex (branching, dynamic task generation, custom operators), or you need
portability across clouds. Common in data-engineering-first orgs.

**The honest answer for this project:** ADF is the right production choice here
— Azure-native, managed identity, no infra overhead. Airflow is included to
demonstrate orchestrator-agnostic design thinking, not because it's better.

---

## Phase 3 Checklist

- [x] Resource group + tags
- [x] ADLS Gen2 storage account (`raw` container, hierarchical namespace)
- [x] Key Vault with Snowflake credentials (RBAC-based, managed identity)
- [x] Data Factory instance + managed identity
- [x] ADF pipeline: HTTP → ADLS → Snowflake external stage → COPY INTO
- [x] Scheduled trigger (daily) + Azure Monitor failure alert
- [x] Airflow DAG (local Docker) — same logical pipeline for comparison
- [x] ADF vs Airflow tradeoff writeup
- [x] ARM template export
