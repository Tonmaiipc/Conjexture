import os
from mem0 import Memory
from typing import Optional

MEM0_ORG_ID = os.getenv("MEM0_ORG_ID", "ctxpool-org")

MEM0_LLM_BASE_URL = os.getenv("MEM0_LLM_BASE_URL", "http://localhost:1234/v1")
MEM0_LLM_MODEL = os.getenv("MEM0_LLM_MODEL", "qwen3-27b")
MEM0_EMBEDDING_BASE_URL = os.getenv("MEM0_EMBEDDING_BASE_URL", "http://localhost:1234/v1")
MEM0_EMBEDDING_MODEL = os.getenv("MEM0_EMBEDDING_MODEL", "nomic-embed-text")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ctxpool")

def _get_memory():
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": MEM0_LLM_MODEL,
                "openai_base_url": MEM0_LLM_BASE_URL,
                "api_key": "not-needed",
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": MEM0_EMBEDDING_MODEL,
                "openai_base_url": MEM0_EMBEDDING_BASE_URL,
                "api_key": "not-needed",
            }
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": QDRANT_HOST,
                "port": QDRANT_PORT,
                "collection_name": QDRANT_COLLECTION,
            }
        }
    }
    return Memory.from_config(config)


def mem0_search_memory(query: str) -> str:
    """
    Search org knowledge memory for information relevant to the query.
    
    Args:
        query: The search query to find relevant memories.
    
    Returns:
        A string containing relevant memories, or a message indicating none were found.
    """
    m = _get_memory()
    results = m.search(query, user_id=MEM0_ORG_ID)
    if not results:
        return "No relevant memories found."
    lines = []
    for r in results:
        stored_at = r["created_at"]
        source_ts = r.get("metadata", {}).get("source_timestamp", "unknown")
        lines.append(f"[stored: {r['created_at']}, source: {source_ts}] {r['memory']}")
    return "\n".join(lines)


def mem0_write_memory(content: str, source_timestamp: Optional[str] = None) -> str:
    """
    Store a finding in org memory.

    Args:
        content: The information to store.
        source_timestamp: ISO datetime when the source information was current (e.g. "2026-04-27T14:30:00Z").

    Returns:
        A confirmation message.
    """
    m = _get_memory()
    metadata = {"source_timestamp": source_timestamp} if source_timestamp else {}
    m.add(content, user_id=MEM0_ORG_ID, metadata=metadata)
    return "Memory stored successfully."