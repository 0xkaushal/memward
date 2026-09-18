#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${MEMWARD_REPO_URL:-https://github.com/0xkaushal/memward.git}"
INSTALL_ROOT="${MEMWARD_INSTALL_ROOT:-$HOME/.memward}"
APP_DIR="$INSTALL_ROOT/app"
DATABASE_CHOICE=""

info() {
  printf '[memward] %s\n' "$1"
}

fail() {
  printf '[memward] Error: %s\n' "$1" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing required command: $1"
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  local env_file="$3"

  if grep -qE "^${key}=" "$env_file"; then
    perl -0pi -e "s|^${key}=.*$|${key}=${value}|m" "$env_file"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

prompt_env_value() {
  local key="$1"
  local prompt_text="$2"
  local secret="${3:-false}"
  local current_value=""

  if [ -f "$APP_DIR/.env" ]; then
    current_value="$(perl -ne 'print "$1\n" if /^'"$key"'=(.*)$/' "$APP_DIR/.env" | tail -n 1)"
  fi

  if [ -n "$current_value" ] && [ "$current_value" != "sk-or-v1-..." ] && [ "$current_value" != "postgresql://postgres:password@db.your-project.supabase.co:5432/postgres" ]; then
    info "$key already set in .env"
    return
  fi

  if [ "$secret" = "true" ]; then
    printf '[memward] %s: ' "$prompt_text"
    stty -echo
    IFS= read -r input_value
    stty echo
    printf '\n'
  else
    printf '[memward] %s: ' "$prompt_text"
    IFS= read -r input_value
  fi

  if [ -z "$input_value" ]; then
    fail "$key is required to continue."
  fi

  set_env_value "$key" "$input_value" "$APP_DIR/.env"
}

prompt_mode() {
  info "Choose install mode:"
  PS3='Select install mode: '
  select selected_mode in "local"; do
    if [ -n "$selected_mode" ]; then
      break
    fi
    info "Please choose a valid install mode."
  done

  set_env_value "MEMWARD_MODE" "$selected_mode" "$APP_DIR/.env"
}

prompt_database_choice() {
  info "Choose database:"
  PS3='Select database: '
  select selected_db in "local" "supabase"; do
    if [ -n "$selected_db" ]; then
      break
    fi
    info "Please choose a valid database option."
  done

  DATABASE_CHOICE="$selected_db"
}

info "Checking required tools..."
require_command git
require_command uv
require_command node
require_command npm

info "Preparing install directory at $INSTALL_ROOT"
mkdir -p "$INSTALL_ROOT"

if [ -d "$APP_DIR/.git" ]; then
  info "Existing install found. Updating repository..."
  git -C "$APP_DIR" pull --ff-only
else
  if [ -e "$APP_DIR" ]; then
    fail "$APP_DIR exists but is not a git checkout. Remove it or set MEMWARD_INSTALL_ROOT."
  fi

  info "Cloning repository from GitHub..."
  git clone "$REPO_URL" "$APP_DIR"
fi

info "Installing Python dependencies..."
uv sync --project "$APP_DIR"

info "Installing UI dependencies..."
npm --prefix "$APP_DIR/ui" install

if [ ! -f "$APP_DIR/.env" ]; then
  info "Creating .env from .env.example..."
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
else
  info "Keeping existing .env file."
fi

prompt_mode
prompt_database_choice

if [ "$DATABASE_CHOICE" = "supabase" ]; then
  prompt_env_value "SUPABASE_DB_URL" "Enter your Supabase/Postgres connection string"
else
  info "Using local SQLite database under ~/.memward/."
fi

prompt_env_value "LLM_API_KEY" "Enter your LLM API key" "true"

cat <<EOF

[memward] Install complete.

App location:
  $APP_DIR

Next steps:
1. Start the app:
   cd "$APP_DIR"
   ./start.sh

2. Open the curation UI:
   http://127.0.0.1:5173

Note:
- Local mode stores state under ~/.memward/.
- Supabase/Postgres is only required when you choose the hosted database path.

EOF
