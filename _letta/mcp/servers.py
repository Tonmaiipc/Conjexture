import os
from anyio import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

SLACK_MCP_API_KEY = os.getenv("SLACK_MCP_API_KEY", "mocked-secret-token-for-dev")

MCP_SERVERS = [
    {
        "server_name": "slack-mcp",
        "config": {
            "mcp_server_type": "streamable_http",
            "server_url": "http://ctxpool-slack-mcp:3001/mcp",
            "auth_header": "Authorization",
            "auth_token": "mocked-secret-token-for-dev"
        }
    }
    # future: jira-mcp, confluence-mcp, etc.
]