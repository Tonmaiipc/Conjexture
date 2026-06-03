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
    import psycopg2

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
        "history_db_path": "/root/.mem0/history.db",
    }
    org_id = os.environ["MEM0_ORG_ID"]
    m = Memory.from_config(config)
    results = m.search(query, filters={"user_id": org_id}, limit=100)
    
    if not results:
        return "No relevant memories found."
    
    # Log the query and whether it was a hit (found any results) to the database
    hit = bool(results.get("results"))
    try:
        conn = psycopg2.connect(os.environ["MEM0_DB_URI"])
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO query_logs (query, mem0_hit) VALUES (%s, %s)",
            (query, hit)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

    # format the output
    lines = []    
    for record in results.get("results", []):
        if record is None:
            continue
        
        # Update hit count and last hit timestamp in metadata
        try:
            from qdrant_client import QdrantClient
            q = QdrantClient(
                host=os.environ["QDRANT_HOST"],
                port=int(os.environ["QDRANT_PORT"]),
            )
            collection = os.environ["QDRANT_COLLECTION"]
            existing = record.get("metadata") or {}
            q.set_payload(
                collection_name=collection,
                payload={
                    "hit_count": existing.get("hit_count", 0) + 1,
                    "last_hit": datetime.now(timezone.utc).isoformat(),
                },
                points=[record["id"]],
            )
        except Exception as e:
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
    import json

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
        "history_db_path": "/root/.mem0/history.db",
        "custom_fact_extraction_prompt": custom_fact_extraction_prompt,
    }

    org_id = os.environ["MEM0_ORG_ID"]
    m = Memory.from_config(config)
    metadata = {}
    if source_timestamp is not None:
        from datetime import datetime
        try:
            datetime.fromisoformat(source_timestamp)
            metadata["source_timestamp"] = source_timestamp
        except Exception:
            return json.dumps({
                "status": "error",
                "content": f"Invalid source_timestamp format: '{source_timestamp}'. Expected ISO 8601 (e.g. '2026-06-01T14:30:00Z').",
            })
    return str(m.add(content, user_id=org_id, metadata=metadata))