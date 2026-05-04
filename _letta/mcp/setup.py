import os
from anyio import Path
from dotenv import load_dotenv
from letta_client import Letta
from _letta.mcp.servers import MCP_SERVERS

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

LETTA_BASE_URL = os.getenv("LETTA_URL", "http://localhost:8283")

def main():
    # Register Slack MCP server
    client = Letta(base_url=LETTA_BASE_URL)

    print("Cleaning up existing MCP server registrations...")
    for old_server in client.mcp_servers.list():
        client.mcp_servers.delete(old_server.id)
        print(f"  Deleted: {old_server.server_name} ({old_server.id})")

    print("Registering MCP servers...")
    for new_server in MCP_SERVERS:
        server = client.mcp_servers.create(**new_server)
        print(f"  Registered: {server.server_name} {server.id}")
    print("Done.")