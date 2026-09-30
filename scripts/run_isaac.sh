#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${ISAAC_PYTHON:-}" || ! -x "$ISAAC_PYTHON" ]]; then
  echo "Set ISAAC_PYTHON to an existing Isaac Sim 4.5 python.sh (or its Python executable)." >&2
  echo "The asset .venv is not an Isaac Sim runtime." >&2
  exit 2
fi
exec "$ISAAC_PYTHON" "$PROJECT_DIR/scripts/smoke_isaac.py" "$@"
