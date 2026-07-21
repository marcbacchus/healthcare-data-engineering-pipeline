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
1. Snowflake text-to-SQL (schema-aware prompt, SQL validation, row-limit guard)
2. Databricks readmission risk endpoint (Phase 4 live model)
3. RAG over clinical reference PDFs — extends the slice above

Plus a Streamlit UI, Docker packaging, deployment to Azure Container Apps
(scale-to-zero), and evaluation documented in `docs/evaluation.md`.
