from dotenv import load_dotenv
import os
import sys
import json
import requests
from pathlib import Path

ROOT = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent / "definitions"

load_dotenv(ROOT / ".env")

LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8283")
LETTA_PASSWORD = os.getenv("LETTA_SERVER_PASSWORD", "")

def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers

def get_all_agents():
    r = requests.get(f"{LETTA_URL}/v1/agents", headers=get_headers())
    r.raise_for_status()
    return r.json()

def delete_agent(agent_id):
    r = requests.delete(f"{LETTA_URL}/v1/agents/{agent_id}", headers=get_headers())
    r.raise_for_status()

def create_agent(payload):
    r = requests.post(
        f"{LETTA_URL}/v1/agents",
        headers=get_headers(),
        json=payload,
    )
    if not r.ok:
        print(f"  ERROR: {r.json().get('detail', r.text)}")
        sys.exit(1)
    return r.json()

def get_tool_map() -> dict:
    r = requests.get(f"{LETTA_URL}/v1/tools", headers=get_headers())
    r.raise_for_status()
    return {t["name"]: t["id"] for t in r.json()}

def main():
    # Delete all existing agents
    print("Deleting existing agents...")
    for agent in get_all_agents():
        print(f"  Deleting {agent['name']} ({agent['id']})")
        delete_agent(agent["id"])

    # Fetch tool map once
    tool_map = get_tool_map()

    # Create agents from JSON files
    print("Creating agents...")
    agent_files = sorted(
        f for f in AGENTS_DIR.glob("*.json")
        if not f.name.startswith("_")
    )

    if not agent_files:
        print("  No agent files found in agents/")
        sys.exit(1)

    for agent_file in agent_files:
        payload = json.loads(agent_file.read_text())
        name = payload.get("name", agent_file.stem)

        tools = payload.pop("tools", [])
        if tools:
            missing = [n for n in tools if n not in tool_map]
            if missing:
                print(f"  ERROR: Tools not registered: {missing}. Run ./go tools-register first.")
                sys.exit(1)
            payload["tool_ids"] = [tool_map[n] for n in tools]

        print(f"  Creating {name}...")
        result = create_agent(payload)
        print(f"  Created {name} ({result['id']})")

    print("Done.")

if __name__ == "__main__":
    main()