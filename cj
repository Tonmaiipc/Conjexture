#!/usr/bin/env bash
set -euo pipefail
if [ -f ".env" ]; then
  set -a
  source ".env"
  set +a
fi

COMPOSE_FILE="docker-compose.yml"
BACKUP_DIR="./backups"
ENV_FILE=".env"
INIT_DIR="./init"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()    { echo -e "${GREEN}[conjexture]${NC} $1"; }
warn()   { echo -e "${YELLOW}[conjexture]${NC} $1"; }
error()  { echo -e "${RED}[conjexture]${NC} $1"; exit 1; }
header() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

require() {
  command -v "$1" &>/dev/null || error "'$1' is required but not installed."
}

_env_get() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true
}

_check_env() {
  [ -f "$ENV_FILE" ] || error "$ENV_FILE not found. Copy .env.example to .env and fill in your values."

  # At least one provider must be configured
  local has_provider=false
  for var in OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY LMSTUDIO_BASE_URL OLLAMA_BASE_URL; do
    local val
    val=$(_env_get "$var")
    [ -n "$val" ] && has_provider=true
  done

  "$has_provider" || error "No LLM provider configured in $ENV_FILE. Set at least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, LMSTUDIO_BASE_URL, OLLAMA_BASE_URL"
}

# infra setup
_log_llm_config() {
  log "Configured providers:"
  for var in OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY LMSTUDIO_BASE_URL OLLAMA_BASE_URL; do
    local val
    val=$(_env_get "$var")
    [ -n "$val" ] && log "  ✓ ${var}"
  done
}

_wait_healthy() {
  local container="$1"
  local timeout="$2"
  local elapsed=0

  while [ $elapsed -lt $timeout ]; do
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "not found")
    if [ "$status" = "healthy" ]; then
      log "$container is healthy"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  warn "$container did not become healthy within ${timeout}s — check logs with: ./cj logs $container"
}

_docker_compose() {
  local profiles=($1)
  shift
  local args=()
  for p in "${profiles[@]:-}"; do
    args+=("--profile" "$p")
  done
  docker compose "${args[@]}" -f "$COMPOSE_FILE" "$@"
}

_parse_profiles() {
  local profiles=()
  for arg in "$@"; do
    case "$arg" in
      --search) profiles+=("search") ;;
      --slack)  profiles+=("slack") ;;
      --jira)   profiles+=("jira") ;;
      --all)    profiles+=("search" "slack" "jira") ;;  # add all known profiles here
    esac
  done

  # deduplicate
  local unique=()
  for p in "${profiles[@]:-}"; do
    [[ " ${unique[*]:-} " == *" $p "* ]] || unique+=("$p")
  done

  echo "${unique[*]:-}"
}

cmd_build() {
  header "Building Conjexture images"
  require docker
  docker build -f Dockerfile.letta -t conjexture-letta:latest .
  log "Done. Run ./cj init' or './cj up' to start."
}

cmd_init() {
  local profiles
  profiles=$(_parse_profiles "--all")

  header "Initializing Conjexture"
  require docker
  _check_env
  _log_llm_config

  # Ensure mem0 history db host file exists (Docker file bind mounts require it)
  local mem0_db_path="${MEM0_HISTORY_DB_PATH:-./backups/mem0-history/history.db}"
  mkdir -p "$(dirname "$mem0_db_path")" && touch "$mem0_db_path"
  log "Ensured mem0 history db exists at $mem0_db_path"

  log "Pulling Docker images..."
  _docker_compose "$profiles" pull --ignore-buildable

  cmd_build

  log "Starting services..."
  _docker_compose "$profiles" up -d

  log "Waiting for services to be healthy..."
  _wait_healthy "conjexture-letta-db" 30
  _wait_healthy "conjexture-mem0-db" 30

  cmd_letta_reset_register

  log "Done. Letta ADE available at http://localhost:8283"
}

cmd_up() {
  local profiles
  profiles=$(_parse_profiles "$@")

  header "Starting Conjexture"
  _check_env
  _log_llm_config

  # Ensure mem0 history db host file exists (Docker file bind mounts require it)
  local mem0_db_path="${MEM0_HISTORY_DB_PATH:-./backups/mem0-history/history.db}"
  mkdir -p "$(dirname "$mem0_db_path")" && touch "$mem0_db_path"
  log "Ensured mem0 history db exists at $mem0_db_path"

  _docker_compose "$profiles" up -d
  log "Services started. Letta ADE at http://localhost:8283"
}

cmd_down() {
  local profiles
  profiles=$(_parse_profiles "$@")
  echo "profiles: '$profiles'"

  header "Stopping Conjexture"
  _docker_compose "$profiles" down
  log "Services stopped."
}

cmd_restart() {
  local profiles
  profiles=$(_parse_profiles "$@")

  header "Restarting Conjexture"
  _docker_compose "$profiles" restart
  log "Services restarted."
}

cmd_reset() {
  local profiles
  profiles=$(_parse_profiles "$@")
  
  header "Resetting Conjexture"
  warn "This will DELETE all volumes and data. Are you sure? (y/N)"
  read -r confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }

  _docker_compose "$profiles" down -v
  log "Volumes deleted. Restarting fresh..."
  _docker_compose "$profiles" up -d
  log "Reset complete."
}

cmd_logs() {
  local service="${1:-}"
  if [ -n "$service" ]; then
    docker compose -f "$COMPOSE_FILE" logs -f "$service"
  else
    docker compose -f "$COMPOSE_FILE" logs -f
  fi
}

cmd_status() {
  header "Conjexture Status"
  docker compose -f "$COMPOSE_FILE" ps
}

cmd_backup() {
  header "Backing up Conjexture databases"
  local timestamp
  timestamp=$(date +%Y%m%d_%H%M%S)
  local backup_path="$BACKUP_DIR/$timestamp"
  mkdir -p "$backup_path"

  log "Backing up letta-db..."
  docker exec conjexture-letta-db \
    pg_dump -U letta letta \
    > "$backup_path/letta-db.sql"

  log "Backing up mem0-db..."
  docker exec conjexture-mem0-db \
    pg_dump -U mem0 mem0 \
    > "$backup_path/mem0-db.sql"

  log "Backup saved to $backup_path"
}

cmd_restore() {
  header "Restoring Conjexture databases"
  local backup_path="${1:-}"

  if [ -z "$backup_path" ]; then
    if [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
      error "No backups found in $BACKUP_DIR"
    fi
    echo "Available backups:"
    ls -1 "$BACKUP_DIR"
    echo ""
    read -rp "Enter backup timestamp to restore: " backup_path
    backup_path="$BACKUP_DIR/$backup_path"
  fi

  [ -d "$backup_path" ] || error "Backup not found: $backup_path"

  warn "This will overwrite current data. Are you sure? (y/N)"
  read -r confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }

  log "Restoring letta-db..."
  docker exec -i conjexture-letta-db \
    psql -U letta letta \
    < "$backup_path/letta-db.sql"

  log "Restoring mem0-db..."
  docker exec -i conjexture-mem0-db \
    psql -U mem0 mem0 \
    < "$backup_path/mem0-db.sql"

  log "Restore complete."
}

cmd_letta_shell() {
  header "Letta DB Shell"
  docker exec -it conjexture-letta-db psql -U letta -d letta
}

cmd_mem0_shell() {
  header "mem0 DB Shell"
  docker exec -it conjexture-mem0-db psql -U mem0 -d mem0
}

# letta setup
cmd_letta_agents_register() {
  header "Registering Agents"
  [ -f "_letta/agents/setup.py" ] || error "_letta/agents/setup.py not found"
  python3 setup.py --agents
}

cmd_letta_tools_register() {
  header "Registering Tools"
  [ -f "_letta/tools/setup.py" ] || error "_letta/tools/setup.py not found"
  python3 setup.py --tools
}

cmd_letta_mcp_register() {
  header "Registering MCP Servers"
  [ -f "_letta/mcp_out/setup.py" ] || error "_letta/mcp_out/setup.py not found"
  python3 setup.py --mcp
}

cmd_letta_register_all() {
  python3 setup.py --all
}

cmd_letta_reset_register() {
  python3 setup.py --all --reset
}

cmd_jira_oauth() {
  header "Jira OAuth Setup"
  : "${ATLASSIAN_OAUTH_CLIENT_ID:?Please set ATLASSIAN_OAUTH_CLIENT_ID in .env}"
  : "${ATLASSIAN_OAUTH_CLIENT_SECRET:?Please set ATLASSIAN_OAUTH_CLIENT_SECRET in .env}"

  docker run --rm -it \
    -p 8080:8080 \
    -v "$(pwd)/.mcp-atlassian:/home/app/.mcp-atlassian" \
    -e ATLASSIAN_OAUTH_CLIENT_ID="${ATLASSIAN_OAUTH_CLIENT_ID}" \
    -e ATLASSIAN_OAUTH_CLIENT_SECRET="${ATLASSIAN_OAUTH_CLIENT_SECRET}" \
    -e ATLASSIAN_OAUTH_REDIRECT_URI="${ATLASSIAN_OAUTH_REDIRECT_URI:-http://localhost:8080/callback}" \
    ghcr.io/sooperset/mcp-atlassian:latest \
    --oauth-setup -v
  log "OAuth setup complete. Run './cj up --jira' to start the Jira MCP server or ./cj up --all to start all services."
}

cmd_help() {
  echo ""
  echo "Usage: ./cj <command>"
  echo ""
  echo "Before running: copy .env.example to .env and fill in your values."
  echo ""
  echo "Infrastructure:"
  echo "  build                   Build custom Docker images (run before first init)"
  echo "  init                    First-time setup — create dirs, pull images, start services"
  echo "  up                      Start all services"
  echo "  down                    Stop all services"
  echo "  restart                 Restart all services"
  echo "  reset                   Stop, delete all volumes, restart fresh (destructive)"
  echo ""
  echo "Development:"
  echo "  logs [service]          Tail logs (all services, or a specific one)"
  echo "  status                  Show service status, health, and active LLM config"
  echo ""
  echo "Data:"
  echo "  backup                  Dump all DB states to ./backups/<timestamp>/"
  echo "  restore [path]          Restore DBs from a backup"
  echo ""
  echo "Shells:"
  echo "  letta-shell             Open psql into letta-db"
  echo "  mem0-shell              Open psql into mem0-db"
  echo ""
  echo "Registeration:"
  echo "  letta-tools-reg         Register tools"
  echo "  letta-mcp-reg           Register MCP servers"
  echo "  letta-agents-reg        Register agents"
  echo "  letta-all-reg           Register tools, mcp servers, and agents"
  echo "  letta-reset-reg         Remove and register conjexture tools, mcp servers, and agents"
  echo ""
  echo "Integration:"
  echo "  jira-oauth              Setup Jira OAuth"
}

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  build)              cmd_build ;;
  init)               cmd_init "$@" ;;
  up)                 cmd_up "$@" ;;
  down)               cmd_down "$@" ;;
  restart)            cmd_restart "$@" ;;
  reset)              cmd_reset "$@" ;;
  logs)               cmd_logs "${1:-}" ;;
  status)             cmd_status ;;
  ps)                 cmd_status ;;
  backup)             cmd_backup ;;
  restore)            cmd_restore "${1:-}" ;;
  letta-shell)        cmd_letta_shell ;;
  mem0-shell)         cmd_mem0_shell ;;
  letta-tools-reg)    cmd_letta_tools_register ;;
  letta-mcp-reg)      cmd_letta_mcp_register ;;
  letta-agents-reg)   cmd_letta_agents_register ;;
  letta-all-reg)      cmd_letta_register_all ;;
  letta-reset-reg)    cmd_letta_reset_register ;;
  jira-oauth)         cmd_jira_oauth ;;
  help|--help)        cmd_help ;;
  *)                  error "Unknown command: $COMMAND. Run './cj help' for usage." ;;
esac
