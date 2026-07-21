"""
Embed fct_adverse_events documents and persist to a local ChromaDB vector store.

Run once to build the store. Subsequent runs detect the existing collection
and skip re-embedding — idempotent by default.

Embedding model: text-embedding-3-small (OpenAI)
  Why: strong quality/cost ratio for semantic similarity; $0.02/1M tokens means
  5K documents (~40 tokens avg) costs ~$0.004 — negligible.

Vector store: ChromaDB (local, persisted to disk)
  Why: no managed service to configure, survives process restarts, and the
  LangChain wrapper exposes it directly as a retriever for the LCEL chain.
  In Phase 5 this would be replaced with a managed store (Azure AI Search,
  Pinecone, etc.) for production scale.
"""

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

sys.path.insert(0, str(Path(__file__).parent))
from data_prep import fetch_documents

load_dotenv(find_dotenv())

CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "faers_adverse_events"
EMBED_MODEL = "text-embedding-3-small"


def build_vectorstore(limit: int = 5000, force_rebuild: bool = False) -> Chroma:
    """
    Build (or load) the ChromaDB vector store.

    Args:
        limit: number of FAERS records to embed (default 5000)
        force_rebuild: if True, drop existing collection and re-embed

    Returns:
        A Chroma instance ready to use as a retriever.
    """
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)

    if not force_rebuild and CHROMA_DIR.exists():
        store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DIR),
        )
        existing = store.get()
        if existing["ids"]:
            print(f"Loaded existing ChromaDB collection: {len(existing['ids'])} documents.")
            return store

    print(f"Fetching {limit} documents from Snowflake...")
    docs = fetch_documents(limit=limit)

    estimated_tokens = len(docs) * 40
    estimated_cost = estimated_tokens / 1_000_000 * 0.02
    print(f"Embedding {len(docs)} documents with {EMBED_MODEL}...")
    print(f"Estimated OpenAI cost: ~${estimated_cost:.4f}")

    if CHROMA_DIR.exists() and force_rebuild:
        import shutil
        shutil.rmtree(CHROMA_DIR)
        print("Dropped existing collection.")

    store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
    )

    final_count = len(store.get()["ids"])
    print(f"Done. {final_count} documents persisted to {CHROMA_DIR}")
    return store


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()

    build_vectorstore(limit=args.limit, force_rebuild=args.force_rebuild)
