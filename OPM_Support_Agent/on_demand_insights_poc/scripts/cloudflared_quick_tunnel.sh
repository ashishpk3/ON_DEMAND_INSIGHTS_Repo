#!/usr/bin/env bash
# Prints a temporary https://*.trycloudflare.com URL when cloudflared is installed:
#   brew install cloudflare/cloudflare/cloudflared
#
# Run FastAPI first (uvicorn on 127.0.0.1:8890), then:
#   bash scripts/cloudflared_quick_tunnel.sh
#
set -euo pipefail

HOST="${INSIGHTS_HOST:-127.0.0.1}"
PORT="${INSIGHTS_PORT:-8890}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Install cloudflared (e.g. brew install cloudflare/cloudflare/cloudflared)." >&2
  exit 1
fi

exec cloudflared tunnel --url "http://${HOST}:${PORT}"
