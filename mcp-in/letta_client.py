"""
Conjexture MCP Server — Letta API client layer.
Configuration, HTTP helpers, response builders, and Letta API operations.
"""
import json
import os
import time
import httpx


LETTA_URL = os.getenv("LETTA_URL", "http://letta:8283")
LETTA_PASSWORD = os.getenv("LETTA_PASSWORD", "")
MCP_CLIENT_TIMEOUT = int(os.getenv("MCP_CLIENT_TIMEOUT", "180"))
AGENT_NAME = "mcp-investigator"


def _get_client(timeout=60):
    """Create an httpx client with shared base config."""
    return httpx.Client(timeout=timeout, follow_redirects=True)


client = _get_client(MCP_CLIENT_TIMEOUT)


def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers


def _error(content, topic_id=None, error_details=None):
    d = {"status": "error", "content": content}
    if topic_id is not None:
        d["topic_id"] = topic_id
    if error_details is not None:
        d["error_details"] = error_details
    return json.dumps(d)


def _debug(content, topic_id=None):
    d = {"status": "debug", "content": content}
    if topic_id is not None:
        d["topic_id"] = topic_id
    return json.dumps(d)


def _success(content, topic_id=None):
    d = {"status": "success", "content": content}
    if topic_id is not None:
        d["topic_id"] = topic_id
    return json.dumps(d)


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
                return " ".join(
                    block.get("text", "")
                    for block in content
                    if block.get("type") == "text"
                )
            elif isinstance(content, str):
                return content
    return None


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
