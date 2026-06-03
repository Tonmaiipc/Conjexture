"""
Conjexture MCP Server — inbound: external LLM clients → Conjexture investigator.
"""
import sys
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

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


def _query_mem0(conversation_id: str, question: str) -> str:
    """Send a mem0-only query to the investigator for a fast preliminary answer."""
    print("Starting phase 1, prelim mem0.", file=sys.stderr)
    try:
        status, text = _send_message(conversation_id, f"Mode: mem0_only\n\n{question}")
        if status == 200:
            messages = parse_sse_messages(text)
            result = extract_assistant_message(messages)
            return _success(
                "Preliminary result: " + result if result else f"No preliminary information found. Continue researching in background. Please check back using the topic ID: {conversation_id}",
                topic_id=conversation_id,
            )
        else:
            return _error(
                f"Letta API error: {status}",
                topic_id=conversation_id,
                error_details=text,
            )
    except Exception as e:
        return _error(f"Failed to reach investigator: {e}", topic_id=conversation_id)


def _dispatch_background(conversation_id: str, research_thoroughly: bool) -> None:
    """Fire-and-forget a full background investigation. Never raises."""
    if research_thoroughly:
        msg = "The user requested thorough research. Investigate fully regardless of cached results."
    else:
        msg = "Review the Phase 1 result. If mem0 already fully answered the question, skip investigation and respond directly. Otherwise, investigate further using available tools."

    with _get_client(5) as fire_client:
        try:
            body = {
                "messages": [{
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "text", "text": f"Mode: full_investigation\n\n{msg}"}],
                }],
                "background": True,
                "streaming": True,
            }
            r = fire_client.post(
                f"{LETTA_URL}/v1/conversations/{conversation_id}/messages",
                headers={**get_headers(), "Accept": "text/event-stream"},
                json=body,
            )
            print(f"Dispatched full investigation. Status: {r.status_code}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Phase 2 error: {e}", file=sys.stderr, flush=True)


@mcp.tool()
def conjexture_query(question: str, topic_id: str | None = None, research_thoroughly: bool = False) -> str:
    """Query Conjexture's org knowledge.

    Responds in two phases:
    1. Preliminary answer (fast): searches mem0 and conversation history
       for existing knowledge. Returns immediately.
    2. Full investigation (background): dispatched automatically. The
       investigator decides whether deeper research is needed based on
       the preliminary result — if mem0 already fully answered the
       question, it may skip investigation unless research_thoroughly
       is set.

    Use the returned topic_id to continue this conversation later with
    follow-up questions.

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
        try:
            r = client.post(
                f"{LETTA_URL}/v1/conversations/",
                params={"agent_id": agent_id},
                headers=get_headers(),
                json={"summary": question[:100]},
            )
            if r.status_code != 200:
                return _error(
                    "Failed to create conversation. This is a server side error.",
                    error_details=r.text,
                )
            conversation_id = r.json()["id"]
        except Exception as e:
            return _error(
                "Failed to create conversation. This is a server side error.",
                error_details=str(e),
            )

    result = _query_mem0(conversation_id, question)
    _dispatch_background(conversation_id, research_thoroughly)
    return result


if __name__ == "__main__":
    import os

    wait_for_letta()

    mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("MCP_PORT", "8300"))

    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn

        app = mcp.streamable_http_app()
        uvicorn.run(app, host=mcp_host, port=mcp_port)
