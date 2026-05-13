"""
Conjexture MCP Server — inbound: external LLM clients → Conjexture investigator.
"""
import sys
import json
import os
import time
import httpx
from mcp.server.fastmcp import FastMCP

LETTA_URL = os.getenv("LETTA_URL", "http://letta:8283")
LETTA_PASSWORD = os.getenv("LETTA_PASSWORD", "")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8300"))
AGENT_NAME = "mcp-investigator"

from mcp.server.transport_security import TransportSecuritySettings

# DNS rebinding protection is enabled by default (production).
# Set DISABLE_DNS_REBINDING_PROTECTION=true to disable for testing behind proxies (ngrok, etc.).
disable = os.getenv("DISABLE_DNS_REBINDING_PROTECTION", "").lower() in ("true", "1")
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=not disable
)

mcp = FastMCP("conjexture", transport_security=transport_security)
client = httpx.Client(timeout=60, follow_redirects=True)

def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers


def find_agent() -> str | None:
    """Find the mcp-investigator agent by name."""
    try:
        r = client.get(f"{LETTA_URL}/v1/agents", headers=get_headers())
        if r.status_code != 200:
            return None
        agents = r.json()
        for agent in agents:
            if agent.get("name") == AGENT_NAME:
                return agent["id"]
    except Exception:
        pass
    return None

def parse_sse_messages(text: str) -> list:
    messages = []
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                messages.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return messages

def extract_assistant_message(messages: list) -> str | None:
    for msg in reversed(messages):
        if msg.get("message_type") == "assistant_message":
            content = msg.get("content", "")
            if isinstance(content, list):
                return " ".join(block.get("text", "") for block in content if block.get("type") == "text")
            elif isinstance(content, str):
                return content
    return None


@mcp.tool()
def conjexture_query(question: str, topic_id: str | None = None) -> str:
    """Query Conjexture's org knowledge. Returns cached answer immediately
    if available, and starts a full background investigation for fresh results.
    Use conjexture_retrieve to retrieve the full investigation results later.

    Args:
        question: The question to research.
        topic_id: The ID of the topic to continue research.
    """
    conversation_id = topic_id

    agent_id = find_agent()
    if not agent_id:
        return json.dumps({
            "status": "error",
            "content": "mcp-investigator agent not found. This is a server side error.",
            "topic_id": None,
        })

    # Create a fresh conversation for this investigation
    if not conversation_id:
        try:
            r = client.post(
                f"{LETTA_URL}/v1/conversations/",
                params={"agent_id": agent_id},
                headers=get_headers(),
                json={"summary": question[:100]},
            )
            if r.status_code != 200:
                return json.dumps({
                    "status": "error",
                    "content": f"Failed to create conversation. This is a server side error.",
                    "error_details": r.text,
                    "topic_id": None,
                })
            conversation_id = r.json()["id"]
        except Exception as e:
            return json.dumps({
                "status": "error",
                "content": f"Failed to create conversation. This is a server side error.",
                "error_details": str(e),
                "topic_id": None,
            })

    # Phase 1: mem0 check — sync
    print(f"Starting phase 1, prelim mem0.", file=sys.stderr)
    try:
        r = client.post(
            f"{LETTA_URL}/v1/conversations/{conversation_id}/messages",
            headers=get_headers(),
            json={
                "messages": [{
                    "role": "user",
                    "content": [{"type": "text", "text": f"Mode: mem0_only\n\n{question}"}],
                }],
            },
        )
        if r.status_code == 200:
            messages = parse_sse_messages(r.text)
            result = extract_assistant_message(messages)
            result = {
                "status": "success",
                "content": "Preliminary result: " + result if result else f"No preliminary information found. Continue researching in background. Please check back using the topic ID: {conversation_id}",
                "topic_id": conversation_id,
            }
        else:
            result = {
                "status": "error",
                "content": f"Letta API error: {r.status_code}",
                "error_details": r.text,
                "topic_id": conversation_id,
            }
    except Exception as e:
        return json.dumps({
            "status": "error",
            "content": f"Failed to reach investigator: {e}",
            "topic_id": conversation_id,
        })
    print(f"Phase 1 completed, string phase2, full investigation.", file=sys.stderr)

    # Phase 2: dispatch full investigation — returns immediately
    with httpx.Client(timeout=5) as fire_client:
        try:
            fire_result = fire_client.post(
                f"{LETTA_URL}/v1/conversations/{conversation_id}/messages",
                headers={**get_headers(), "Accept": "text/event-stream"},
                json={
                    "messages": [{
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "text", "text": "Mode: full_investigation\n\nContinue the investigation beyond mem0."}],
                    }],
                    "background": True,
                    "streaming": True,
                }
            )
            print(f"Dispatched full investigation. Status: {fire_result.status_code}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Phase 2 error: {e}", file=sys.stderr, flush=True)

    return json.dumps(result)


@mcp.tool()
def conjexture_retrieve(investigation_subject: str, topic_id: str) -> str:
    """Attempt to retrieve the previously requested investigation.

    Args:
        investigation_subject: The subject of the investigation you want to retrieve.
        topic_id: The topic ID returned by conjexture_query.
    """
    conversation_id = topic_id

    if not conversation_id:
        return json.dumps({"status": "error", "content": "No topic ID provided."})

    try:
        r = client.post(
            f"{LETTA_URL}/v1/conversations/{conversation_id}/messages",
            headers=get_headers(),
            json={
                "messages": [{
                    "role": "user",
                    "content": [{"type": "text", "text": f"Mode: info_retrieval\n\n{investigation_subject}"}],
                }],
            },
        )
        if r.status_code != 200:
            return json.dumps({
                "status": "error",
                "content": f"Failed to connect to the conversation. This is a server side error.",
                "error_details": r.text,
                "topic_id": conversation_id,
            })

        messages = parse_sse_messages(r.text)

        result = extract_assistant_message(messages)
        if result:
            return json.dumps({
                "status": "success",
                "content": result,
                "topic_id": conversation_id,
            })
        else:
            return json.dumps({
                "status": "success",
                "content": "Investigation is still in progress. Check again later.",
                "topic_id": conversation_id,
            })

    except Exception as e:
        return json.dumps({
            "status": "error", 
            "content": f"Failed to check investigation: {e}", 
            "topic_id": conversation_id}
        )


def wait_for_letta(max_retries=30, delay=2):
    """Wait for Letta API to be ready and find the mcp-investigator agent."""
    for i in range(max_retries):
        agent_id = find_agent()
        if agent_id:
            return
        time.sleep(delay)
    raise RuntimeError(
        f"Letta API not ready or '{AGENT_NAME}' agent not found "
        f"after {max_retries * delay}s. "
        f"Ensure the stack is running and './cj letta-reset-reg' has been run."
    )


if __name__ == "__main__":

    wait_for_letta()

    # Default: run as HTTP SSE server (for Docker HTTP clients, Cursor, etc.)
    # With "stdio" arg: run as stdio server (for Claude Desktop via docker exec)
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
