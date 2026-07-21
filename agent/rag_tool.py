"""
Wraps rag_chain.get_chain() as a LangChain @tool for the ReAct agent.

The chain itself already does the real work (retrieval, grounding, source
citation via Report ID) — this module's only job is exposing it with a tool
description the agent can use for routing, and caching the chain so it's
built once per process rather than once per call (get_chain() reloads the
ChromaDB collection from disk each time it's invoked).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rag_chain import get_chain

from langchain_core.tools import tool

_chain = None


def _get_cached_chain():
    global _chain
    if _chain is None:
        _chain = get_chain()
    return _chain


@tool
def rag_adverse_event_search(question: str) -> str:
    """
    Answer open-ended or narrative questions about individual FDA adverse event
    (FAERS) reports by retrieving and grounding on the most similar report
    excerpts. Good for "tell me about", "were there reports involving X",
    pattern/theme questions over a handful of reports. Cites Report IDs.

    NOT good for aggregate/statistical questions (counts, totals, "which is
    most common") — similarity search returns semantically similar reports,
    not a representative sample, so those questions should use the SQL tool
    instead.
    """
    return _get_cached_chain().invoke(question)


if __name__ == "__main__":
    import sys as _sys

    q = " ".join(_sys.argv[1:]) or "Were there reports involving elderly patients?"
    print(f"Q: {q}\n")
    print(rag_adverse_event_search.invoke(q))
