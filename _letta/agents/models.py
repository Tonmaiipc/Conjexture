import sys

from pydantic import BaseModel


class AgentDefinition(BaseModel):
    name: str
    model: str
    embedding: str
    agent_type: str = "memgpt_agent"
    include_base_tools: bool = True
    include_multi_agent_tools: bool = False
    description: str | None = None
    block_ids: list[str] = []
    tools: list[str] = []

class AgentPayload(BaseModel):
    name: str
    model: str
    embedding: str
    agent_type: str = "memgpt_agent"
    include_base_tools: bool = True
    include_multi_agent_tools: bool = False
    description: str | None = None
    block_ids: list[str] = []
    tool_ids: list[str] = []
    memory_blocks: list = []
    system: str

def to_payload(definition: AgentDefinition, tool_map: dict, prompt_map: dict) -> AgentPayload:
    prompt = prompt_map.get(definition.name)
    if not prompt:
        print(f"  ERROR: No prompt file found for '{definition.name}'")
        sys.exit(1)
    
    missing = [t for t in definition.tools if t not in tool_map]
    if missing:
        print(f"  ERROR: Tools not registered: {missing}")
        sys.exit(1)
    
    return AgentPayload(
        name=definition.name,
        model=definition.model,
        embedding=definition.embedding,
        agent_type=definition.agent_type,
        include_base_tools=definition.include_base_tools,
        include_multi_agent_tools=definition.include_multi_agent_tools,
        description=definition.description,
        block_ids=definition.block_ids,
        tool_ids=[tool_map[t] for t in definition.tools],
        memory_blocks=[],
        system=prompt,
    )

class AgentSetupResult(BaseModel):
    created: dict[str, str] = {}
    updated: dict[str, str] = {}

    @property
    def all(self) -> dict[str, str]:
        return {**self.created, **self.updated}