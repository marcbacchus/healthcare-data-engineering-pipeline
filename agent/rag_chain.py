"""
LCEL RAG chain: retriever | prompt | LLM.

The chain is explicit about each step — retriever pulls top-k documents from
ChromaDB, format_docs serialises them with source IDs for citation, the prompt
grounds the LLM in that context, and StrOutputParser returns a plain string.

LLM: claude-haiku-4-5 (cheap for prototyping, swap model= for Sonnet in demo)
Retriever: ChromaDB similarity search, k=5
"""

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

sys.path.insert(0, str(Path(__file__).parent))
from ingest import build_vectorstore

load_dotenv(find_dotenv())

_SYSTEM_PROMPT = """\
You are a healthcare data analyst reviewing FDA adverse event reports (FAERS).

Answer the question using ONLY the report excerpts provided in the context below.
When citing evidence, reference the Report ID (e.g. "Report 24381169 shows...").
If the context does not contain enough information to answer, say so explicitly — \
do not guess, extrapolate, or draw on outside knowledge.

Dataset limitation: these reports contain demographic and geographic fields only \
(age, sex, country, reporter type, report date). Drug names and reaction descriptions \
were not loaded in this dataset. Questions about specific drugs or medical outcomes \
cannot be answered from this data alone.\
"""

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)

_LLM = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)


def _format_docs(docs: list[Document]) -> str:
    """Serialise retrieved documents with their report IDs for source citation."""
    return "\n\n".join(
        f"[Report {doc.metadata.get('report_id', 'unknown')}] {doc.page_content}"
        for doc in docs
    )


def get_chain(k: int = 5):
    """
    Build and return the RAG chain.

    The chain is a LangChain LCEL pipeline:
      retriever → format_docs ──┐
                                ├── prompt → LLM → StrOutputParser
      RunnablePassthrough ──────┘

    Args:
        k: number of documents to retrieve per query (default 5)

    Returns:
        A runnable chain that accepts a question string and returns an answer string.
    """
    store = build_vectorstore()
    retriever = store.as_retriever(search_kwargs={"k": k})

    chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | _PROMPT
        | _LLM
        | StrOutputParser()
    )
    return chain


if __name__ == "__main__":
    chain = get_chain()
    test_q = "What proportion of reports came from outside the United States?"
    print(f"Q: {test_q}\n")
    print(chain.invoke(test_q))
