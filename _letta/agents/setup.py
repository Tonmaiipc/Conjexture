from dotenv import load_dotenv
import os
import sys
import json
import requests
from pathlib import Path
from _letta.agents.models import AgentDefinition, AgentPayload, AgentSetupResult, to_payload


ROOT = Path(__file__).parent.parent.parent
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

def request_existing_agents() -> dict:
    r = requests.get(f"{LETTA_URL}/v1/agents", headers=get_headers())
    r.raise_for_status()
    return {a["name"]: a["id"] for a in r.json()}

def delete_agent(agent_id):
    r = requests.delete(f"{LETTA_URL}/v1/agents/{agent_id}", headers=get_headers())
    r.raise_for_status()

def delete_existing_agents(existing_agents: dict | None = None):
    # Delete all existing agents
    print("Cleaning up existing agents...")
    for agent_name, agent_id in (existing_agents or request_existing_agents()).items():
        print(f"  Deleting {agent_name} ({agent_id})")
        delete_agent(agent_id)

def request_tool_map_from_letta_host() -> dict:
    r = requests.get(f"{LETTA_URL}/v1/tools?limit=1000", headers=get_headers())
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

def build_agent_payloads(tool_map: dict) -> list[AgentPayload]:
    definitions = read_agent_definitions()
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

def inject_investigator_memory_block(payload: AgentPayload, investigator_id: str) -> AgentPayload:
    block = {
        "label": "user_support_agent_registry",
        "value": json.dumps({"investigator_id": investigator_id}),
        "description": "Registry of agent IDs for inter-agent communication.",
        "read_only": True
    }
    return payload.model_copy(update={"memory_blocks": [block]})

def create_agent(payload: AgentPayload) -> dict:
    print(f"  Registering {payload.name}...")
    result = post_agent(payload)
    print(f"  Registered {payload.name} ({result['id']})")
    return result

def register_new_agents(tool_map: dict) -> AgentSetupResult:
    print("Registering agents...")
    payloads = {p.name: p for p in build_agent_payloads(tool_map)}

    investigator = create_agent(payloads["investigator"])
    mcp_investigator = create_agent(payloads["mcp-investigator"])
    
    user_support_payload = inject_investigator_memory_block(
        payloads["user-support"], 
        investigator["id"]
    )
    user_support = create_agent(user_support_payload)

    return AgentSetupResult(created={
        "investigator": investigator["id"],
        "user-support": user_support["id"],
        "mcp-investigator": mcp_investigator["id"]
    })

def update_existing_agents(existing_agents: dict, new_agent_payloads: list[AgentPayload]) -> AgentSetupResult:
    # Update existing agents with new definitions
    print("Updating existing agents...")
    updated = {}
    for payload in new_agent_payloads:
        agent_id = existing_agents.get(payload.name)
        if not agent_id:
            print(f"  No existing agent found for {payload.name}, creating a new agent.")
            result = post_agent(payload)
            print(f"  Created {payload.name} ({result['id']})")
            updated[payload.name] = result['id']
            continue
        print(f"  Updating {payload.name} ({agent_id})...")
        result = requests.patch(
            f"{LETTA_URL}/v1/agents/{agent_id}",
            headers=get_headers(),
            json=payload.model_dump( exclude_none=True, by_alias=True )
        )
        if not result.ok:
            print(f"  ERROR updating {payload.name}: {result.json().get('detail', result.text)}")
            sys.exit(1)
        print(f"  Updated {payload.name} ({agent_id})")
        updated[payload.name] = agent_id
    return AgentSetupResult(updated=updated)

def main(reset: bool = False) -> AgentSetupResult:
    tool_map = request_tool_map_from_letta_host()
    existing_agents = request_existing_agents()

    if reset:
        delete_existing_agents(existing_agents)
        impacted_agents = register_new_agents(tool_map)
    elif existing_agents:
        print("Existing agents found:")
        print("\n".join(f"  {name} ({agent_id})" for name, agent_id in existing_agents.items()))
        update_agent_payloads = build_agent_payloads(tool_map)
        impacted_agents = update_existing_agents(existing_agents, update_agent_payloads)
    else:        
        print("No existing agents found. Registering new agents...")
        impacted_agents = register_new_agents(tool_map)
    print("Done.")

    return impacted_agents