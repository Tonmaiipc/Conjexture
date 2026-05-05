import os
from anyio import Path
from dotenv import load_dotenv
import requests
from _letta.mcp.servers import MCP_SERVERS

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

LETTA_BASE_URL = os.getenv("LETTA_URL", "http://localhost:8283")
LETTA_PASSWORD = os.getenv("LETTA_PASSWORD", "password")

def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers

def main():
    headers = get_headers()
    # Delete existing MCP server registrations
    print("Cleaning up existing MCP server registrations...")
    servers = requests.get(f"{LETTA_BASE_URL}/v1/mcp-servers/", headers=headers).json()
    for server in servers:
        requests.delete(f"{LETTA_BASE_URL}/v1/mcp-servers/{server['id']}", headers=headers)
        print(f"  Deleted: {server['server_name']} ({server['id']})")

    # Register new MCP servers
    print("Registering MCP servers...")
    for new_server in MCP_SERVERS:
        r = requests.post(f"{LETTA_BASE_URL}/v1/mcp-servers/", headers=headers, json=new_server)
        server = r.json()
        print(f"  Registered: {server['server_name']} {server['id']}")
    print("Done.")