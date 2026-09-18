#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${MEMWARD_REPO_URL:-https://github.com/0xkaushal/memward.git}"
INSTALL_ROOT="${MEMWARD_INSTALL_ROOT:-$HOME/.memward}"
APP_DIR="$INSTALL_ROOT/app"

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

cat <<EOF

[memward] Install complete.

App location:
  $APP_DIR

Next steps:
1. Edit $APP_DIR/.env and set your credentials.
   Current required setup includes:
   - SUPABASE_DB_URL
   - LLM_API_KEY

2. Start the app:
   cd "$APP_DIR"
   ./start.sh

3. Open the curation UI:
   http://127.0.0.1:5173

Note:
- This installer matches the current Supabase-based setup.
- The planned local-mode database under ~/.memward/ is not implemented yet.

EOF
