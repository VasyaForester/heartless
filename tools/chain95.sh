#!/usr/bin/env bash
# chain95 — giftcard v47: «expired gift cards, zero balance, коллекционные»
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain95-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Diamond Whale Bold"  inputs/lbp-giftcard-v47-expired-dw.txt giftcard-v47-expired-DW
run christmas-giftcard-scam "Sand Ant Plus Ultra" inputs/lbp-giftcard-v47-expired-sa.txt giftcard-v47-expired-SA
echo "== chain95 done ==" | tee -a "$LOG"