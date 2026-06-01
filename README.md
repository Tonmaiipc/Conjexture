# Conjexture

**Org Memory Platform** — a self-hosted, memory-first knowledge consolidation platform for engineering teams.

**Conjexture** connects to your org's tools (Slack, Jira, Confluence, and more), investigates questions on your behalf, and stores findings in a shared memory that grows smarter with every query. The more your team asks, the faster and cheaper subsequent queries become.

> "Your org knowledge compounds. Stop searching, start knowing."


## Why **Conjexture**?

Most org knowledge tools are search-first and stateless — they find information but don't learn from queries. 

1. **Conjexture** is memory-first:
- **Glean, Dust, Rovo, Notion AI** — search returns results, session ends, nothing is remembered
- **Conjexture** — every investigation is stored back to shared memory, making the next query faster and cheaper.

**The system compounds over time.**

2. **SaaS agnostic** — connects to your existing tools, no ecosystem lock-in
3. **LLM agnostic** — bring your own API key, swap models anytime
4. **Self-hosted** — your data never leaves your infrastructure


## How It Works

```
┌─────────────────────────────────────────────────────┐
│         External LLM Clients                         │
│  (Claude Desktop, Cursor, other MCP hosts)           │
└─────────────────┬───────────────────────────────────┘
                  │ conjexture_query / conjexture_retrieve
┌─────────────────▼───────────────────────────────────┐
│           conjexture-mcp (port 8300)                 │
│      FastMCP server — StreamableHTTP                 │
│      Dispatches to mcp-investigator via Letta API    │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                    User / Frontend                   │
│              (Letta ADE, Slack bot)                  │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              User-Support Agent (Letta)              │
│         Conversational interface, dispatches         │
└─────────────────┬───────────────────────────────────┘
                  │ dispatch_to_investigator
┌─────────────────▼───────────────────────────────────┐
│          Investigator / mcp-investigator (Letta)     │
│                                                      │
│  1. Check mem0 (shared org memory)                   │
│  2. If insufficient → fan out to tools               │
│  3. Store findings to mem0                           │
│  4. Return answer to caller                          │
└──┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
 mem0       Slack      Jira/      Web
(Qdrant)   (MCP)    Confluence  (SearXNG)
                      (MCP)

Next query on same topic → mem0 hit → investigation skipped

The closed loop is the core value: every investigation makes the next one faster.


## Features

- **Memory-first retrieval** — shared org knowledge grows from queries, not manual curation
- **Multi-source investigation** — Slack, Jira, Confluence, web search in a single query
- **Self-hosted** — your data never leaves your infrastructure
- **Subagent architecture** — user-support agent dispatches to investigator asynchronously
- **Conversation isolation** — each topic gets its own investigator conversation, preventing context accumulation
- **Timestamps on every memory** — staleness is visible, not hidden

---

## Architecture

<img width="795" height="634" alt="image" src="https://github.com/user-attachments/assets/ec0720eb-4e42-4579-8371-7195a1fb6008" />


## Agents

| Agent | Role | Model |
|-------|------|-------|
| `user-support` | User-facing, receives queries, dispatches to investigator, presents answers | DeepSeek V4 Flash |
| `investigator` | Checks mem0, fans out to tools, stores findings, returns results to user-support | DeepSeek V4 Flash |
| `mcp-investigator` | Same capacity as `investigator` but responds directly in-conversation; used by the `conjexture-mcp` server for two-phase querying (mem0-only fast path + background full investigation) | DeepSeek V4 Flash |


## Stack

| Component | Purpose |
|-----------|---------|
| [Letta](https://github.com/letta-ai/letta) | Agent runtime, orchestration, conversational context |
| [mem0](https://github.com/mem0ai/mem0) | Shared org knowledge store, semantic retrieval |
| [Qdrant](https://qdrant.tech) | Vector backend for mem0 |
| PostgreSQL + pgvector | Letta state (letta-db) and mem0 metadata (mem0-db) |
| [SearXNG](https://github.com/searxng/searxng) | Self-hosted web search |
| [korotovsky/slack-mcp-server](https://github.com/korotovsky/slack-mcp-server) | Slack MCP server |
| [sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian) | Jira + Confluence MCP server |
| conjexture-mcp (mcp-in/) | FastMCP server exposing `conjexture_query` and `conjexture_retrieve` tools over StreamableHTTP (port 8300); dispatches to mcp-investigator via the Letta API |


## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- API keys (see [Configuration](#configuration))

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/your-org/conjexture.git
cd conjexture
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys and configuration. See [Configuration](#configuration) for details.

### 3. Setup Dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the stack

call the provided cj bash script to setup the infrastructure, tools, mcp servers, and agents.

```bash
./cj init
```

This will:
- Pull all Docker images
- Start all services
- Wait for health checks to pass

### 5. Start chatting

1. Open the Letta ADE at [https://app.letta.com](https://app.letta.com) and completes the registration
2. On the top left menubar, click on the Default Project drop down. Select **Managed Projects**
3. Select **Self-Hosted servers**, then **Connect to a server**.
4. In **Server URL**, enter your local letta url (default: `http://localhost:8283`), and Password if set. Then click **Confirm**.
5. Your local server should appear on the Self-Hosted servers list. Select it to enter its management panel.
6. Select **View agents** or **agents** menu item. The registered agents **user-support**, **investigator**, and **mcp-investigator** should appear.
7. Select **Open in ADE** of the **user-support** agent to start chatting.

---

## Configuration

> **Note:** This configuration guide covers local development and self-hosted deployment.
> For production deployment (ECS, Kubernetes, managed cloud), you will need to adapt
> environment variable injection to your infrastructure's secrets management system
> (AWS Secrets Manager, Vault, etc.) and replace the Docker Compose DB containers
> with managed database services (RDS, Cloud SQL, etc.).

Copy `.env.example` to `.env` and fill in the required values.

### Required

```bash
# LLM Provider — pick one

# recommended well tested setup
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
USER_SUPPORT_AGENT_MODEL=deepseek/deepseek-v4-flash
INVESTIGATOR_AGENT_MODEL=deepseek/deepseek-v4-flash
LETTA_EMBEDDING_MODEL=openai/text-embedding-3-small

# mem0 LLM (for memory extraction)
# Uses OpenRouter as a unified gateway. Mem0 only accepts one API key for both LLM and embeddings.
# Note: OpenRouter is not an official mem0 provider but works via openai-compatible mode.
MEM0_LLM_MODEL=deepseek/deepseek-v4-flash
MEM0_LLM_BASE_URL=https://openrouter.ai/api/v1 
MEM0_LLM_API_KEY=sk-...
MEM0_EMBEDDING_MODEL=nomic-embed-text
MEM0_EMBEDDING_BASE_URL=http://host.docker.internal:1234/v1
MEM0_ORG_ID=your-org-name

```

### Slack Integration

```bash
# Run ./go up --slack to enable
SLACK_MCP_XOXB_TOKEN=xoxb-...   # Bot token
SLACK_MCP_XOXP_TOKEN=xoxp-...   # User token (required for search)
SLACK_MCP_API_KEY=your-secret   # Internal auth key for MCP server
```

To create a Slack app and get tokens, see [Slack Setup](#slack-setup).

### Jira + Confluence Integration

**Option A — API Token (recommended, simpler)**

```bash
# Run ./go up --jira to enable
JIRA_URL=https://your-org.atlassian.net
JIRA_USERNAME=your-email@org.com
JIRA_API_TOKEN=your-api-token
CONFLUENCE_URL=https://your-org.atlassian.net/wiki
CONFLUENCE_USERNAME=your-email@org.com
CONFLUENCE_API_TOKEN=your-api-token
```

**Option B — OAuth 2.0 (more secure, requires one-time browser setup)**

```bash
ATLASSIAN_OAUTH_ENABLE=true
ATLASSIAN_OAUTH_CLIENT_ID=your-client-id
ATLASSIAN_OAUTH_CLIENT_SECRET=your-client-secret
ATLASSIAN_OAUTH_CLOUD_ID=your-cloud-id
ATLASSIAN_OAUTH_REDIRECT_URI=http://localhost:8080/callback
ATLASSIAN_OAUTH_SCOPE=read:issue:jira read:project:jira read:content:confluence offline_access
JIRA_URL=https://your-org.atlassian.net
CONFLUENCE_URL=https://your-org.atlassian.net/wiki
```

Run `./cjx jira-oauth` once to complete the OAuth flow before starting the Jira MCP server.

To get Atlassian's tokens, see [Atlassian Setup](#jira-auth-setup).

---

## Services & Profiles

Services are grouped into Docker Compose profiles:

```bash
./ctx up              # Core stack only (letta, databases, qdrant)
./ctx up --search     # + SearXNG web search
./ctx up --slack      # + Slack MCP server
./ctx up --jira       # + Jira/Confluence MCP server
./ctx up --all        # Everything
```


### Slack Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From a manifest**
2. Paste the manifest from `slack-app-manifest.json` in this repo
3. Click **Install to Workspace**
4. Copy the **Bot User OAuth Token** (`xoxb-...`) and **User OAuth Token** (`xoxp-...`) to your `.env`
5. Join the channels you want Conjexture to have access


### Atlassian Auth Setup 

**Option A**
1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Give it a name (e.g. `Conjexture`) and set an expiration date (max 365 days)
4. Copy the token immediately — it won't be shown again
5. Add to your `.env`:

```bash
ATLASSIAN_USERNAME=atlassian-registered@email.com
JIRA_URL=https://your-org.atlassian.net
JIRA_API_TOKEN=your-api-token
CONFLUENCE_URL=https://your-org.atlassian.net/wiki
CONFLUENCE_API_TOKEN=your-api-token
```

> **Note:** If you select **Create API token** optoin, the same API token works for both Jira and Confluence. `CONFLUENCE_API_TOKEN` and `JIRA_API_TOKEN` should be the same value.

> **Token expiry:** Atlassian API tokens expire after a maximum of 365 days. Set a calendar reminder to rotate before expiry to avoid service interruption.

**Option B**
1. Create an OAuth 2.0 app at [developer.atlassian.com/console/myapps](https://developer.atlassian.com/console/myapps)
2. Add callback URL: `http://localhost:8080/callback`
3. Add required scopes (see `.env.example`)
4. Copy Client ID and Secret to `.env`
5. Run `./go jira-oauth` and complete the browser flow
6. Tokens are stored in `.mcp-atlassian/` — gitignored

For remote server deployment, run `./go jira-oauth` locally and copy `.mcp-atlassian/` to your server.

---

## External Client Access (Claude Desktop, Cursor, etc.)

The `conjexture-mcp` server exposes two MCP tools on port 8300 by default:

- **`conjexture_query(question, topic_id?)`** — Checks mem0 (fast, <1s), returns preliminary result + topic_id. Simultaneously dispatches a full background investigation.
- **`conjexture_retrieve(investigation_subject, topic_id)`** — Poll the background investigation results using the topic_id from conjexture_query.

### Option A — Direct Docker Connection (no network exposure)

Claude Desktop can connect directly to the container over Docker networking:

```json
{
  "mcpServers": {
    "conjexture": {
      "command": "docker",
      "args": ["exec", "-i", "conjexture-mcp", "python", "main.py", "stdio"]
    }
  }
}
```

This runs the server in stdio mode, so Claude Desktop talks to it via `docker exec`. Requires the `conjexture-mcp` container to be running.

### Option B — Non-Local Network Server

If Claude Desktop is running on a different machine (or you want to expose the service):

1. Ensure port 8300 or your custom port is accessible from the client machine (network routing, firewall, or a tunnel like ngrok)
2. Configure Claude Desktop:

```json
{
  "mcpServers": {
    "conjexture": {
      "type": "url",
      "url": "http://<host>:8300/mcp"
    }
  }
}
```

Replace `<host>` with the Docker host IP or tunnel URL. The server speaks StreamableHTTP natively — no supergateway or additional bridge needed.

### Cursor and Other Clients

Any MCP host that supports StreamableHTTP (or can wrap stdio via `docker exec`) can use conjexture-mcp. Point it to port 8300 with the `/mcp` path, or use the direct docker pattern above.

---

## Production Deployment

Production deployment is out of scope for this guide. At a high level:

- Replace `letta-db` and `mem0-db` containers with managed Postgres (RDS, Supabase, Neon)
- Deploy services to your compute platform of choice (ECS Fargate, EC2, Kubernetes)
- Use your infrastructure's secrets management for environment variables
- Use a container registry (ECR, GCR) for custom images
- Terraform templates coming soon

---

## Roadmap

**Done**
- [x] User-support + investigator agent loop
- [x] mem0 shared knowledge store
- [x] Web search via SearXNG
- [x] Slack integration via MCP
- [x] Jira + Confluence integration via MCP
- [x] Conversation-per-topic isolation
- [x] mem0 hit/miss loop proven
- [x] Agent reliability testing — 10 query pair test suite
- [x] mem0 write quality audit — manually inspect what's stored
- [x] mem0 hit rate instrumentation
- [x] Conjexture exposed as an MCP tool for Claude Desktop, Cursor, and other LLM clients

**Next**
- [ ] Stale memory handling — contradictory memories strategy
- [ ] Source provenance on mem0 writes — source, timestamp, captured_by
- [ ] Document Slack token scope — public channels only

**Team Engagement**
- [ ] Slack bot — passive ingestion
- [ ] Frontend — research-dispatch-centric chat UI
- [ ] Multi-user support

**Future**
- [ ] Sleep-time memory consolidation agent
- [ ] Memory decay and cleanup
- [ ] Notion, Google Drive, git connectors
- [ ] Proactive insights ("three teams are solving the same problem")

**Enterprise**
- [ ] Multi-tenant architecture

---

## License

MIT

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

*Built with [Letta](https://github.com/letta-ai/letta) and [mem0](https://github.com/mem0ai/mem0).*
