#!/usr/bin/env bash
# PG auto-ping watchdog (participant instruction 2026-11-10): every 15 min emit a
# PG-AUTOPING line so the owning session is notified and can resume/continue solving.
# Read-only: never touches the browser or the arena tab.
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
LOG="artifacts/pg-autoping.log"
while true; do
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  LAST="$(ls -t artifacts/pg-chain*.log 2>/dev/null | head -1)"
  echo "[$TS] ping ok | last chain log: ${LAST:-none}" >> "$LOG"
  echo "PG-AUTOPING $TS"
  sleep 900
done
