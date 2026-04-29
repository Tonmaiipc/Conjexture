import os
import sys
import inspect
import requests
from pathlib import Path
from dotenv import load_dotenv
import mem0_tools

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8283")
LETTA_PASSWORD = os.getenv("LETTA_SERVER_PASSWORD", "")

def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers

def upsert_tool(source_code: str, description: str, tags: list, pip_requirements: list):
    r = requests.put(
        f"{LETTA_URL}/v1/tools",
        headers=get_headers(),
        json={
            "source_type": "python",
            "source_code": source_code,
            "description": description,
            "tags": tags,
            "pip_requirements": pip_requirements,
        }
    )
    if not r.ok:
        print(f"  ERROR: {r.json().get('detail', r.text)}")
        sys.exit(1)
    return r.json()

def main():
    tools = [
        {
            "func": mem0_tools.mem0_search_memory,
            "description": "Search org knowledge memory for information relevant to a query.",
            "tags": ["custom", "mem0"],
            "pip_requirements": [{"name": "mem0ai"}],
        },
        {
            "func": mem0_tools.mem0_write_memory,
            "description": "Store a finding or piece of knowledge in org memory.",
            "tags": ["custom", "mem0"],
            "pip_requirements": [{"name": "mem0ai"}],
        },
    ]

    print("Registering tools...")
    for tool in tools:
        source_code = inspect.getsource(tool["func"])
        name = tool["func"].__name__
        print(f"  Upserting {name}...")
        result = upsert_tool(source_code, tool["description"], tool["tags"], tool["pip_requirements"])
        print(f"  Done: {result['id']}")

    print("Done.")

if __name__ == "__main__":
    main()