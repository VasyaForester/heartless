#!/usr/bin/env bash
# chain94 — giftcard v46: «EMPTY gift cards» (нулевой баланс — сценарий сам называет «empty» карты)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain94-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v46-empty-sa.txt giftcard-v46-empty-SA
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v46-empty-dw.txt giftcard-v46-empty-DW
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v46-empty-yk.txt giftcard-v46-empty-YK
echo "== chain94 done ==" | tee -a "$LOG"