#!/bin/bash
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace"
export CHAT_TARGET=5ED8D39575C312086CD9EC03254BF9BA
LOG="artifacts/pg-chain39b-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
  echo "== open linkedin =="
  python3 harness/hackathon.py arena open --target "$CHAT_TARGET" --url 'https://app.grayswan.ai/arena/challenge/proving-ground' >/dev/null 2>&1
  node harness/switch-wave.mjs --wave 'Wave 19' >/dev/null 2>&1
  python3 harness/hackathon.py arena select-scenario --target "$CHAT_TARGET" --value linkedin-company-appreciation >/dev/null 2>&1
  echo "== v2 resume x9 =="
  python3 harness/farm.py --target "$CHAT_TARGET" --track Indirect --scenario-id linkedin-company-appreciation --models 'Pink Snail Ultra,Sand Trout Giga,Stone Frog Cosmic,Void Lizard Magical,White Crow Giant,White Salmon Supreme,White Starfish Cosmic,Zinc Beetle Exalted,Zinc Shark Mega' --input inputs/pg-w19-linkedin-v2.txt --scope inputs/pg-scope-w19-v2.json --judge-policy never --pause 16 --opid-prefix pg-w19-v2b --board 'Proving Ground' --ckpt artifacts/pg-w19-v2.json
  echo "== chain39b done =="
} > "$LOG" 2>&1
