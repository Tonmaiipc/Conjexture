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
    from datetime import datetime, timezone        

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
        },
    }
    org_id = os.environ["MEM0_ORG_ID"]
    m = Memory.from_config(config)
    results = m.search(query, filters={"user_id": org_id}, limit=100)
    
    if not results:
        return "No relevant memories found."

    lines = []
    
    for record in results.get("results", []):
        if record is None:
            continue

        try:
            current_metadata = record.get("metadata") or {}
            m.update(
                memory_id=record["id"],
                data=record["memory"],  # text unchanged
                metadata={
                    **current_metadata,
                    "hit_count": current_metadata.get("hit_count", 0) + 1,
                    "last_hit": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception:
            pass  # never let hit counting break retrieval

        source_ts = (record.get("metadata") or {}).get("source_timestamp", "unknown")
        try:
            source_ts = datetime.fromisoformat(source_ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        retrieval_count = (record.get("metadata") or {}).get("hit_count", 0)
        lines.append(f"[sourced: {source_ts}, retrieval_count: {retrieval_count}] {record['memory']}")
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

    custom_fact_extraction_prompt = """
Extract factual knowledge relevant to org operations. Focus on:
- Technical findings (system behavior, bugs, configurations)
- Process outcomes (what happened, when, result)
- Tool and service status
- Decisions made and their rationale

Ignore conversational filler, greetings, and meta-commentary about the investigation process itself.

Return a JSON object with a facts array.
"""

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
        },
        "custom_fact_extraction_prompt": custom_fact_extraction_prompt,
        "history_db_path": os.environ["MEM0_DB_URI"]
    }

    org_id = os.environ["MEM0_ORG_ID"]
    m = Memory.from_config(config)
    metadata = {"source_timestamp": source_timestamp} if source_timestamp else {}
    return str(m.add(content, user_id=org_id, metadata=metadata))