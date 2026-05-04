import json
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

from _letta.agents.models import AgentSetupResult

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8283")
LETTA_PASSWORD = os.getenv("LETTA_PASSWORD", "password")


def get_headers():
    headers = {"Content-Type": "application/json"}
    if LETTA_PASSWORD:
        headers["Authorization"] = f"Bearer {LETTA_PASSWORD}"
    return headers

def request_existing_user_support_agent_registry() -> list[str]:
    r = requests.get(f"{LETTA_URL}/v1/blocks", headers=get_headers())
    r.raise_for_status()
    return [b["id"] for b in r.json() if b["label"] == "user_support_agent_registry"]

def delete_block(block_id):
    r = requests.delete(f"{LETTA_URL}/v1/blocks/{block_id}", headers=get_headers())
    r.raise_for_status()

def build_user_support_agent_registry_block(investigator_id: str) -> dict:
    return {
        "label": "user_support_agent_registry",
        "value": json.dumps({"investigator_id": investigator_id}),
        "description": "Registry of agent IDs for inter-agent communication.",
        "tags": ["registry", "system"],
        "read_only": True
    }

def post_user_support_agent_registry_block(payload: dict) -> dict:
    print(f"Creating user support's agent registry block with {payload['value']}...")
    r = requests.post(
        f"{LETTA_URL}/v1/blocks",
        headers=get_headers(),
        json=payload
    )
    if not r.ok:
        print(f"  ERROR: {r.json().get('detail', r.text)}")
        sys.exit(1)
    print(f"  Created block with id {r.json()['id']}")
    print(f"Done.")
    return r.json()

def associate_investigator_with_user_support(user_support_id: str, investigator_id: str):
    payload = build_user_support_agent_registry_block(investigator_id)
    block = post_user_support_agent_registry_block(payload)
    print(f"Associating block ({block['id']}) with user support ({user_support_id}) containing investigator ({investigator_id})...")
    r = requests.patch(
        f"{LETTA_URL}/v1/agents/{user_support_id}/core-memory/blocks/attach/{block['id']}",
        headers=get_headers(),
    )
    if not r.ok:
        print(f"  ERROR: {r.json().get('detail', r.text)}")
        sys.exit(1)
    print(f"  Associated user support ({user_support_id}) with investigator ({investigator_id}).")
    print(f"Done.")

def create_user_support_agent_registry(user_support_id: str, investigator_id: str):
    existing = request_existing_user_support_agent_registry()
    for block_id in existing:
        delete_block(block_id)
    associate_investigator_with_user_support( user_support_id, investigator_id)

def main(agent_setup: AgentSetupResult):
    if agent_setup.created:
        user_support_id = agent_setup.created.get("user-support")
        investigator_id = agent_setup.created.get("investigator")
        if user_support_id and investigator_id:
            create_user_support_agent_registry(user_support_id, investigator_id)
        else:
            print("Either user support id or investigator agent id is missing. Agent registry failed.")
            sys.exit(1)
    elif agent_setup.updated:
        print("Agents were updated but not created, skipping user support agent registry setup.")