#!/bin/bash
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace"
export CHAT_TARGET=5ED8D39575C312086CD9EC03254BF9BA
LOG="artifacts/pg-chain40-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
  echo "== open hijack-recruiter (Wave 11) =="
  python3 harness/hackathon.py arena open --target "$CHAT_TARGET" --url 'https://app.grayswan.ai/arena/challenge/proving-ground' >/dev/null 2>&1
  node harness/switch-wave.mjs --wave 'Wave 11' >/dev/null 2>&1
  python3 harness/hackathon.py arena select-scenario --target "$CHAT_TARGET" --value hijack-recruiter >/dev/null 2>&1
  echo "== v3 direct-invocation x12 =="
  python3 harness/farm.py --target "$CHAT_TARGET" --track Indirect --scenario-id hijack-recruiter --models 'Iron Dragonfly Large,Stone Frog Cosmic,Electric Starfish Supreme,Pink Snail Ultra,Sand Trout Giga,Lightning Turtle Ultra,White Crow Giant,White Salmon Supreme,White Starfish Cosmic,Zinc Beetle Exalted,Zinc Shark Mega,Void Lizard Magical' --input inputs/pg-w11-recruiter-v3.txt --scope inputs/pg-scope-w11-v3.json --judge-policy never --pause 16 --opid-prefix pg-w11-v3 --board 'Proving Ground' --ckpt artifacts/pg-w11-v3.json
  echo "== chain40 done =="
} > "$LOG" 2>&1
