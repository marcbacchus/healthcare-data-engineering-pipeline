# Phase 5 — RAG AI Agent: LangChain, ChromaDB, Streamlit

## Setup

Use a dedicated venv for this folder — the global Python environment on some
machines has a `starlette`/`fastapi` pin that's too old for Streamlit's actual
import needs, which crashes it at startup with an unrelated-looking
`ImportError`.

```bash
python3 -m venv .venv          # from the repo root
.venv/bin/pip install -r agent/requirements.txt
set -a && source .env && set +a
.venv/bin/streamlit run agent/app.py
```

### Docker

```bash
docker build -f agent/Dockerfile -t healthcare-agent .   # from the repo root

# Source .env into the shell first, then pass vars by name (-e VAR with no
# value pulls from the current shell env). Don't use `docker run --env-file
# .env` directly — Docker's env-file parser doesn't strip quotes the way
# shell `source` / python-dotenv do, and this .env quotes some values
# (SNOWFLAKE_ACCOUNT, etc.). A quoted account identifier fails Snowflake's
# connector validation with a confusing error that looks unrelated to quoting.
set -a && source .env && set +a
docker run -d -p 8501:8501 \
  -e SNOWFLAKE_ACCOUNT -e SNOWFLAKE_USER -e SNOWFLAKE_PASSWORD -e SNOWFLAKE_WAREHOUSE \
  -e OPENAI_API_KEY -e ANTHROPIC_API_KEY -e DATABRICKS_HOST -e DATABRICKS_TOKEN \
  healthcare-agent
```

The image doesn't bake in `agent/chroma_db/` (excluded via `.dockerignore` —
it's local dev state, not a build artifact). A fresh container rebuilds it
from Snowflake + OpenAI embeddings on the RAG tool's first call, same as
locally — the same "pay a one-time cost on cold start" tradeoff as the
Databricks endpoint's own scale-to-zero wake.

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
2. **Databricks readmission risk endpoint** — `databricks_tool.py`. Done.
3. **RAG over adverse event reports** — `rag_tool.py` (wraps the minimal slice
   above as a proper `@tool`). Done.
4. **Agent wiring** — `react_agent.py`. Done.

Remaining: a Streamlit UI, Docker packaging, deployment to Azure Container
Apps (scale-to-zero), and evaluation documented in `docs/evaluation.md`.

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

### Tool 2: Databricks readmission risk endpoint (`databricks_tool.py`)

Takes a natural-language patient description, extracts the model's 8 input
features via structured LLM output (`with_structured_output`, not free-text
parsing), and calls the live `readmission_risk_model` endpoint from Phase 4
(`docs/model_cards.md`, Model 1).

**Refuses rather than guesses:** if the description under-specifies the
patient, the tool lists exactly which required fields are missing instead of
substituting a default risk factor — consistent with the model card's "not
intended for autonomous clinical decision-making" framing. Every response,
regardless of prediction, carries a mandatory disclaimer (synthetic training
data, AUC ~0.51/near-chance, not a diagnosis, requires clinician review).

`expense_to_income_ratio` is computed here with the exact training-time
formula rather than left to the LLM to calculate.

**Auth note:** Databricks personal access tokens are scoped. Calling this
endpoint requires a token with the `model-serving` API scope specifically —
the workspace's token UI returns a generic 403 for insufficient scope, but
the response body names the missing scope exactly
(`"does not have required scopes: model-serving"`).

Run: `python agent/databricks_tool.py "72-year-old patient with 6 active conditions..."`

### Agent wiring (`react_agent.py`)

`langchain.agents.create_agent` (LangGraph-backed) wires all three tools into
one ReAct-style agent: model calls a tool, sees the result, decides whether to
call another or answer — up to a few iterations, not a fixed pipeline.

- **Tool selection** is driven by each tool's own docstring (LangChain surfaces
  these to the model as the tool descriptions); the system prompt adds only the
  rules that cut across all three — don't call the risk model for aggregate
  questions, don't paraphrase away a SQL query or a disclaimer.
- **Source citation:** SQL answers must include the literal query verbatim;
  RAG answers must cite Report IDs (enforced by `rag_chain.py`'s own prompt).
- **Disclaimer integrity:** the Databricks tool's disclaimer must be relayed in
  full, not summarized — verified by testing that the exact disclaimer text
  survives the agent's response.
- **Memory:** `InMemorySaver` checkpointer, keyed by a `thread_id` per
  conversation — confirmed a follow-up like "and which quarter had the fewest?"
  correctly resolves against the prior turn's subject without restating it.

Tested against: correct single-tool routing for all three tools, a mixed
question requiring two tools in one turn (correctly answered one part and
declined the other — payment anomalies aren't exposed via any tool — rather
than fabricating a number), and an adversarial delete request (declined,
explained its tools are read-only, suggested the legitimate path).

Run: `python agent/react_agent.py` (interactive) or
`python agent/react_agent.py "your question"` (single turn)
