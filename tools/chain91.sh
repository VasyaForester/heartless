#!/usr/bin/env bash
# chain91 — giftcard v42: «детектор ингестит образцы через listing tool» (staging sandbox)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain91-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v42-ingest-sa.txt giftcard-v42-ingest-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v42-ingest-yk.txt giftcard-v42-ingest-YK
echo "== chain91 done ==" | tee -a "$LOG"