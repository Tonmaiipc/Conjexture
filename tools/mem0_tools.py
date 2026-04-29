from typing import Optional

def mem0_search_memory(query: str) -> str:
    """
    Search org knowledge memory for information relevant to the query.

    Args:
        query: The search query to find relevant memories.

    Returns:
        A string containing relevant memories with timestamps, or a message indicating none were found.
    """
    import os
    from mem0 import Memory

    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": os.environ["MEM0_LLM_MODEL"],
                "openai_base_url": os.environ["MEM0_LLM_BASE_URL"],
                "api_key": os.environ.get("MEM0_LLM_API_KEY", "not-needed"),
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": os.environ["MEM0_EMBEDDING_MODEL"],
                "openai_base_url": os.environ["MEM0_EMBEDDING_BASE_URL"],
                "api_key": os.environ.get("MEM0_LLM_API_KEY", "not-needed"),
            }
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": os.environ["QDRANT_HOST"],
                "port": int(os.environ["QDRANT_PORT"]),
                "collection_name": os.environ["QDRANT_COLLECTION"],
            }
        }
    }

    org_id = os.environ["MEM0_ORG_ID"]
    m = Memory.from_config(config)
    results = m.search(query, filters={"user_id": org_id})
    
    if not results:
        return "No relevant memories found."

    lines = []
    
    for r in results.get("results", []):
        if r is None:
            continue
        stored_at = r["created_at"]
        source_ts = (r.get("metadata") or {}).get("source_timestamp", "unknown")
        lines.append(f"[stored: {stored_at}, source: {source_ts}] {r['memory']}")
    return "\n".join(lines)


def mem0_write_memory(content: str, source_timestamp: Optional[str] = None) -> str:
    """
    Store a finding or piece of knowledge in org memory.

    Args:
        content: The information to store in memory.
        source_timestamp: ISO datetime when the source information was current (e.g. 2026-04-27T14:30:00Z).

    Returns:
        A confirmation message.
    """
    import os
    from mem0 import Memory

    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": os.environ["MEM0_LLM_MODEL"],
                "openai_base_url": os.environ["MEM0_LLM_BASE_URL"],
                "api_key": os.environ.get("MEM0_LLM_API_KEY", "not-needed"),
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": os.environ["MEM0_EMBEDDING_MODEL"],
                "openai_base_url": os.environ["MEM0_EMBEDDING_BASE_URL"],
                "api_key": os.environ.get("MEM0_LLM_API_KEY", "not-needed"),
            }
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": os.environ["QDRANT_HOST"],
                "port": int(os.environ["QDRANT_PORT"]),
                "collection_name": os.environ["QDRANT_COLLECTION"],
            }
        }
    }

    org_id = os.environ["MEM0_ORG_ID"]
    m = Memory.from_config(config)
    metadata = {"source_timestamp": source_timestamp} if source_timestamp else {}
    return str(m.add(content, user_id=org_id, metadata=metadata))