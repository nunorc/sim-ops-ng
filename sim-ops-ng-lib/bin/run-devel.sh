#!/usr/bin/env bash

SESSION_NAME="sim-ops"

if ! screen -list | grep -q "\.${SESSION_NAME}"; then
  screen -dmS "$SESSION_NAME"

  screen -S "$SESSION_NAME" -X screen bash -c "PYTHONPATH=. uv run bin/sim-ops.py; exec bash"
  screen -S "$SESSION_NAME" -X screen bash -c "PYTHONPATH=. uv run bin/sim-ops-api.py; exec bash"
  screen -S "$SESSION_NAME" -X screen bash -c "PYTHONPATH=. uv run bin/admin.py; exec bash"

  # Optional: rename tabs
  screen -S "$SESSION_NAME" -p 0 -X title "sim"
  screen -S "$SESSION_NAME" -p 1 -X title "api"
  screen -S "$SESSION_NAME" -p 2 -X title "admin"
fi

screen -r "$SESSION_NAME"

