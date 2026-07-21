# Phase 5 — RAG AI Agent: LangChain, ChromaDB, Streamlit

## Minimal RAG slice (working prototype)

A working, eval-tested RAG loop over the `fct_adverse_events` dbt mart:

| File | Role |
|---|---|
| `data_prep.py` | Connects to Snowflake as TRANSFORMER, queries `fct_adverse_events`, builds one LangChain Document per row |
| `ingest.py` | Embeds documents via OpenAI `text-embedding-3-small`, persists to local ChromaDB |
| `rag_chain.py` | LCEL chain: retriever → format_docs → prompt → Claude Haiku → StrOutputParser |
| `run.py` | Interactive CLI (`python agent/run.py`) or preset eval (`python agent/run.py --eval`) |

Grounded in the dbt mart rather than raw FAERS files, so the vector store
inherits the same typing/cleaning guarantees the business relies on.

**Known limitations:** aggregate/statistical questions ("which quarter had
the most reports?") are a weak point for similarity search — that's the gap
the text-to-SQL tool below closes. FAERS demographic data only; drug/reaction
fields aren't loaded yet. Full writeup in `notes/phase5.md`.

## Full Phase 5 build (in progress)

Three tools wired into a LangChain ReAct agent:
1. **Snowflake text-to-SQL** — `sql_tool.py`. Done.
2. Databricks readmission risk endpoint (Phase 4 live model)
3. RAG over clinical reference PDFs — extends the slice above

Plus a Streamlit UI, Docker packaging, deployment to Azure Container Apps
(scale-to-zero), and evaluation documented in `docs/evaluation.md`.

### Tool 1: Snowflake text-to-SQL (`sql_tool.py`)

Generates a SQL SELECT from a natural-language question and runs it against
three new `HEALTHCARE_REPORTING.REPORTING` views (`rpt_provider_payments`,
`rpt_adverse_events`, `rpt_patient_risk` — thin dbt passthroughs of the
Phase 2 marts, added in `dbt/models/reporting/`). Closes the RAG slice's
known weak point on aggregate/statistical questions.

**Two independent guardrail layers**, deliberately redundant:
- **Privilege separation:** runs as the REPORTER Snowflake role — SELECT-only,
  scoped to the REPORTING schema (see `terraform/roles.tf`). REPORTER cannot
  write anywhere, so a bad generation has no write path regardless of what
  the validator catches.
- **SQL validation via `sqlglot`** (AST parsing, not keyword/regex matching —
  those are trivially bypassed by comments, casing, or CTE-wrapped DML):
  exactly one statement, must parse as SELECT, every table reference must be
  one of the three allowed views, and LIMIT is rewritten/injected server-side
  rather than trusted from the LLM.

Run: `python agent/sql_tool.py "which quarter had the most adverse event reports?"`
