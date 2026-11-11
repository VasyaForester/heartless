#!/bin/bash
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace"
export CHAT_TARGET=5ED8D39575C312086CD9EC03254BF9BA
LOG="artifacts/pg-chain41-$(date +%H%M%S).log"
echo "LOG=$LOG"
run_batch () {
  local models="$1" ckpt="$2" prefix="$3"
  python3 harness/hackathon.py arena open --target "$CHAT_TARGET" --url 'https://app.grayswan.ai/arena/challenge/proving-ground' >/dev/null 2>&1
  sleep 2
  node harness/switch-wave.mjs --wave 'Wave 11' >/dev/null 2>&1
  sleep 1
  python3 harness/hackathon.py arena select-scenario --target "$CHAT_TARGET" --value hijack-recruiter >/dev/null 2>&1
  sleep 1
  python3 harness/farm.py --target "$CHAT_TARGET" --track Indirect --scenario-id hijack-recruiter --models "$models" --input inputs/pg-w11-recruiter-v3.txt --scope inputs/pg-scope-w11-v3.json --judge-policy never --pause 16 --opid-prefix "$prefix" --board 'Proving Ground' --ckpt "$ckpt"
}
{
  echo "== batch A: 6 =="
  run_batch 'Stone Frog Cosmic,Electric Starfish Supreme,Pink Snail Ultra,Sand Trout Giga,Lightning Turtle Ultra,White Crow Giant' artifacts/pg-w11-v3a.json pg-w11-v3a
  echo "== batch B: 5 =="
  run_batch 'White Salmon Supreme,White Starfish Cosmic,Zinc Beetle Exalted,Zinc Shark Mega,Void Lizard Magical' artifacts/pg-w11-v3b.json pg-w11-v3b
  echo "== chain41 done =="
} > "$LOG" 2>&1
