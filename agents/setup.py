from dotenv import load_dotenv
import os
import sys
import json
import requests
from pathlib import Path
from models import AgentDefinition, AgentPayload, to_payload


ROOT = Path(__file__).parent.parent
DEFINITIONS_DIR = Path(__file__).parent / "definitions"
PROMPTS_DIR = Path(__file__).parent / "prompts"

load_dotenv(ROOT / ".env")

LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8283")
LETTA_PASSWORD = os.getenv("LETTA_SERVER_PASSWORD", "")

def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers

def get_letta_agents():
    r = requests.get(f"{LETTA_URL}/v1/agents", headers=get_headers())
    r.raise_for_status()
    return r.json()

def delete_agent(agent_id):
    r = requests.delete(f"{LETTA_URL}/v1/agents/{agent_id}", headers=get_headers())
    r.raise_for_status()

def delete_existing_agents():
    # Delete all existing agents
    print("Deleting existing agents...")
    for agent in get_letta_agents():
        print(f"  Deleting {agent['name']} ({agent['id']})")
        delete_agent(agent["id"])

def request_tool_map_from_letta_host() -> dict:
    r = requests.get(f"{LETTA_URL}/v1/tools", headers=get_headers())
    r.raise_for_status()
    return {t["name"]: t["id"] for t in r.json()}

def read_agent_definitions() -> list[AgentDefinition]:
    agent_files = sorted(
        f for f in DEFINITIONS_DIR.glob("*.json")
        if not f.name.startswith("_")
    )
    if not agent_files:
        print(f"  No agent definition files found in {DEFINITIONS_DIR}")
        sys.exit(1)
    return [AgentDefinition(**json.loads(agent_file.read_text())) for agent_file in agent_files]

def read_agent_prompt_map() -> dict:
    prompt_map = {
        f.stem: f.read_text() for f in PROMPTS_DIR.glob("*.txt")
        if not f.name.startswith("_")
    }
    if not prompt_map:
        print(f"  No agent prompt files found in {PROMPTS_DIR}")
        sys.exit(1)
    return prompt_map

def build_agent_payloads() -> list[AgentPayload]:
    definitions = read_agent_definitions()
    tool_map = request_tool_map_from_letta_host()
    prompt_map = read_agent_prompt_map()
    return [to_payload(d, tool_map, prompt_map) for d in definitions]

def post_agent(payload: AgentPayload) -> dict:
    r = requests.post(
        f"{LETTA_URL}/v1/agents",
        headers=get_headers(),
        json=payload.model_dump( exclude_none=True, by_alias=True )
    )
    if not r.ok:
        print(f"  ERROR: {r.json().get('detail', r.text)}")
        sys.exit(1)
    return r.json()

def register_agents() -> dict:
    # Create agents from JSON files
    print("Registering agents...")
    registered_agents = {}
    for agent_definition in build_agent_payloads():
        print(f"  Registering {agent_definition.name}...")
        result = post_agent(agent_definition)
        print(f"  Registered {agent_definition.name} ({result['id']})")
        registered_agents[agent_definition.name] = result['id']
    return registered_agents

def main():
    delete_existing_agents()   
    register_agents()
    print("Done.")

if __name__ == "__main__":
    main()