"""
Conjexture MCP Server — inbound: external LLM clients → Conjexture investigator.
"""
import logging
import sys
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger("conjexture-mcp")

from letta_client import (
    _get_client,
    _error,
    _success,
    client,
    find_agent,
    get_headers,
    parse_sse_messages,
    extract_assistant_message,
    wait_for_letta,
    LETTA_URL,
)

# DNS rebinding protection is enabled by default (production).
# Set DISABLE_DNS_REBINDING_PROTECTION=true to disable for testing behind proxies (ngrok, etc.).
import os
disable = os.getenv("DISABLE_DNS_REBINDING_PROTECTION", "").lower() in ("true", "1")
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=not disable
)

mcp = FastMCP("conjexture", transport_security=transport_security)


def _send_message(conversation_id: str, text: str, background: bool = False) -> tuple[int, str]:
    """Send a message to a Letta conversation. Returns (status_code, response_text)."""
    body = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": text}],
        }],
    }
    if background:
        body["background"] = True
        body["streaming"] = True

    headers = get_headers()
    if background:
        headers = {**headers, "Accept": "text/event-stream"}

    r = client.post(
        f"{LETTA_URL}/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json=body,
    )
    return r.status_code, r.text


def _create_letta_conversation(agent_id: str, question: str) -> str | None:
    """Create a new Letta conversation. Returns conversation_id or None (logs details)."""
    try:
        r = client.post(
            f"{LETTA_URL}/v1/conversations/",
            params={"agent_id": agent_id},
            headers=get_headers(),
            json={"summary": question[:100]},
        )
        if r.status_code != 200:
            logger.error("Failed to create conversation. Status=%s body=%s", r.status_code, r.text)
            return None
        return r.json()["id"]
    except Exception as e:
        logger.error("Failed to create conversation: %s", e)
        return None


def _quick_search(conversation_id: str, question: str) -> str | None:
    """Check conversation history and mem0 for a fast answer. Returns response text or None."""
    logger.info("Quick search (conversation history + mem0)")
    try:
        status, text = _send_message(conversation_id, f"Mode: quick_search\n\n{question}")
        if status != 200:
            logger.error("Letta API error %s: %s", status, text)
            return None
        messages = parse_sse_messages(text)
        return extract_assistant_message(messages)
    except Exception as e:
        logger.error("Failed to reach investigator: %s", e)
        return None


def _dispatch_background(conversation_id: str, question: str, research_thoroughly: bool) -> None:
    """Fire-and-forget a full background investigation. Never raises."""
    if research_thoroughly:
        msg = f"The user requested thorough research.\n\n{question}"
    else:
        msg = question

    with _get_client(5) as fire_client:
        try:
            body = {
                "messages": [{
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "text", "text": f"Mode: investigation\n\n{msg}"}],
                }],
                "background": True,
                "streaming": True,
            }
            r = fire_client.post(
                f"{LETTA_URL}/v1/conversations/{conversation_id}/messages",
                headers={**get_headers(), "Accept": "text/event-stream"},
                json=body,
            )
            logger.info("Dispatched full investigation (status=%s)", r.status_code)
        except Exception as e:
            logger.error("Background dispatch failed: %s", e)


@mcp.tool()
def conjexture_query(question: str, topic_id: str | None = None, research_thoroughly: bool = False) -> str:
    """Query Conjexture's org knowledge.

    Searches conversation history and mem0 for a fast preliminary answer,
    then dispatches a full background investigation if deeper research is
    needed. The investigator decides whether to investigate further based
    on the preliminary result.

    Use the returned topic_id to follow up with the same conversation later.

    Args:
        question: The question to research.
        topic_id: Omit to start a new topic. Provide a topic_id from a
                  previous call to continue that conversation.
        research_thoroughly: Set to True to force a deep investigation
                             even if a cached answer exists in mem0.
    """
    agent_id = find_agent()
    if not agent_id:
        return _error("mcp-investigator agent not found. This is a server side error.")

    conversation_id = topic_id

    # Start a new topic if no topic_id provided
    if not conversation_id:
        conversation_id = _create_letta_conversation(agent_id, question)
        if not conversation_id:
            return _error("Failed to create conversation. This is a server side error.")

    # Quick search: check conversation history + mem0
    result = _quick_search(conversation_id, question)
    if result:
        content = f"Preliminary result: {result}"
    else:
        content = f"No preliminary information found. Continue researching in background. Please check back using the topic ID: {conversation_id}"

    _dispatch_background(conversation_id, question, research_thoroughly)
    return _success(content, topic_id=conversation_id)


if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    wait_for_letta()

    mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("MCP_PORT", "8300"))

    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn

        app = mcp.streamable_http_app()
        uvicorn.run(app, host=mcp_host, port=mcp_port)
