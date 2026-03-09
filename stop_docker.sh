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

if ! command -v docker >/dev/null 2>&1; then
  die "docker command not found."
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  die "docker compose is unavailable."
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

CMD=("${COMPOSE_CMD[@]}")
if ((${#PROFILE_ARGS[@]} > 0)); then
  CMD+=("${PROFILE_ARGS[@]}")
fi
CMD+=(down)
if ((${#EXTRA_ARGS[@]} > 0)); then
  CMD+=("${EXTRA_ARGS[@]}")
fi

"${CMD[@]}"
