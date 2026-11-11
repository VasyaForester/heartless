#!/bin/bash
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace"
export CHAT_TARGET=5ED8D39575C312086CD9EC03254BF9BA
LOG="artifacts/pg-chain38b-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
  echo "== open bypass-spam-filter =="
  python3 harness/hackathon.py arena open --target "$CHAT_TARGET" --url 'https://app.grayswan.ai/arena/challenge/proving-ground' >/dev/null 2>&1
  node harness/switch-wave.mjs --wave 'Wave 9' >/dev/null 2>&1
  python3 harness/hackathon.py arena select-scenario --target "$CHAT_TARGET" --value bypass-spam-filter >/dev/null 2>&1
  echo "== v1b resume x8 =="
  python3 harness/farm.py --target "$CHAT_TARGET" --track Indirect --scenario-id bypass-spam-filter --models 'Obsidian Fox Ultra,Obsidian Grasshopper Bold,Pink Snail Ultra,Ruby Crow Super,Sapphire Flamingo Intrepid,Stone Frog Cosmic,Water Ostrich Gigantic,Zinc Beetle Exalted' --input inputs/pg-w9b-filter-v1.txt --scope inputs/pg-scope-w9b-v1b.json --judge-policy never --pause 16 --opid-prefix pg-w9b-v1b2 --board 'Proving Ground' --ckpt artifacts/pg-w9b-v1b.json
  echo "== chain38b done =="
} > "$LOG" 2>&1
