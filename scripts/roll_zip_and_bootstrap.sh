#!/usr/bin/env bash
set -euo pipefail

# If a plain file named ".venv" exists (historical accident), remove it so a directory can be created.
if [ -f ".venv" ] && [ ! -d ".venv" ]; then
  echo "[bootstrap] Removing stray file .venv so a virtualenv directory can be created"
  rm -f .venv
fi

# Optional ZIP input: pass via env ZIP=/path/to/file.zip
ZIP="${ZIP:-}"

# Use system Python on CI to avoid venv churn on runners.
if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  echo "[bootstrap] CI detected; using runner Python (no venv)"
else
  echo "[bootstrap] Local run; preparing virtualenv"
  if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    . venv/bin/activate
  elif [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    . .venv/bin/activate
  else
    python3 -m venv .venv
    # shellcheck disable=SC1091
    . .venv/bin/activate
  fi
fi

say() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
err() { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

say "Sanity checks"
if [ -n "$ZIP" ]; then
  [ -f "$ZIP" ] || err "Zip not found: $ZIP"
else
  echo "[bootstrap] No ZIP provided; skipping ZIP sanity check"
fi

# …rest of your original script (install deps, build, etc.) …
