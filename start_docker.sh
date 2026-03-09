#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT_DIR"

PROFILE_ARGS=()
EXTRA_ARGS=()

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

warn() {
  echo "[WARN] $*" >&2
}

if ! command -v docker >/dev/null 2>&1; then
  die "docker command not found. Install Docker Desktop/Engine first."
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  die "docker compose is unavailable. Install Docker Compose."
fi

if [[ ! -f docker-compose.yml ]]; then
  die "docker-compose.yml not found in: $ROOT_DIR"
fi

for arg in "$@"; do
  case "$arg" in
    --with-iopaint)
      PROFILE_ARGS+=(--profile iopaint)
      ;;
    *)
      EXTRA_ARGS+=("$arg")
      ;;
  esac
done

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  warn ".env missing. Created from .env.example. Fill API keys and rerun if needed."
fi

mkdir -p data models

CMD=("${COMPOSE_CMD[@]}")
if ((${#PROFILE_ARGS[@]} > 0)); then
  CMD+=("${PROFILE_ARGS[@]}")
fi
CMD+=(up -d --build)
if ((${#EXTRA_ARGS[@]} > 0)); then
  CMD+=("${EXTRA_ARGS[@]}")
fi

"${CMD[@]}"

echo
echo "==================== DOCKER STARTED ===================="
echo "Frontend : http://localhost:3000"
echo "Backend  : http://localhost:8000"
if ((${#PROFILE_ARGS[@]} > 0)); then
  echo "IOPaint  : http://localhost:8090"
fi
echo "Stop all : ./stop_docker.sh"
echo "========================================================"
