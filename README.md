# Conjexture (cj)

A self-hosted org knowledge consolidation platform. Knowledge grows automatically from queries — every investigation result is stored to shared memory, making subsequent queries faster and cheaper.

## How it works

1. Employee asks a question
2. User support agent checks shared memory (mem0) first
3. If found → answer returned immediately
4. If not → agent investigates (web search, connected tools), stores findings, returns answer
5. Next query on the same topic → memory hit, investigation skipped

## Stack

- **Letta** — agent runtime and orchestration
- **mem0** — shared org knowledge store
- **Qdrant** — vector backend for mem0
- **Postgres + pgvector** — Letta state and mem0 metadata (separate containers)
- **LM Studio / Ollama** — optional local LLM serving

## Prerequisites

- Docker + Docker Compose
- At least one LLM provider (see Configuration)

## Getting started

```bash
cp .env.example .env
# Edit .env and configure at least one LLM provider
./cj init
```

Letta ADE will be available at http://localhost:8283.

## Configuration

Copy `.env.example` to `.env` and fill in the providers you want available. At least one is required.

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `LMSTUDIO_BASE_URL` | LM Studio base URL (e.g. `http://host.docker.internal:1234`) |
| `OLLAMA_BASE_URL` | Ollama base URL (e.g. `http://host.docker.internal:11434`) |
| `SECURE` | Set `true` to password-protect the Letta server |
| `LETTA_SERVER_PASSWORD` | Password if `SECURE=true` |
| `LETTA_DB_URI` | Optional — override bundled Postgres for Letta state |
| `MEM0_DB_URI` | Optional — override bundled Postgres for mem0 |

All configured providers are available in the Letta ADE model dropdown. Model selection is per-agent.

**Note on embeddings:** Letta requires an embedding model for archival memory search. OpenAI (`text-embedding-3-small`) and LM Studio (`nomic-embed-text`) both work. Anthropic and OpenRouter do not provide embeddings — if using these as your only provider, you'll also need LM Studio or OpenAI configured for embeddings.

## Commands

```bash
./cj init        # First-time setup — pull images, start services
./cj up          # Start all services
./cj down        # Stop all services
./cj restart     # Restart all services
./cj reset       # Wipe all data and restart (destructive)

./cj logs [svc]  # Tail logs
./cj status      # Service health + active provider config
./cj ps          # Running containers

./cj backup      # Dump databases to ./backups/<timestamp>/
./cj restore     # Restore databases from a backup

./cj letta-shell # psql into letta-db
./cj mem0-shell  # psql into mem0-db
```

## Agent setup

After `./cj init`, run the Python setup script to create the agents:

```bash
cd agents
pip install -r requirements.txt
python setup.py
```

This creates the user support agent and investigator subagent with the models specified in `.env`.

## Architecture

User
└─▶ User Support Agent (Letta)
└─▶ Investigator Agent (Letta)
├─▶ mem0 (shared knowledge store)
└─▶ Tools (web search, future: Slack, JIRA, Notion...)

## License

MIT