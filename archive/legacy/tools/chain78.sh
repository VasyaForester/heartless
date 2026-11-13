#!/usr/bin/env bash
# chain78 — инвентаризация инструментов моков (ищем edit/update/sell-поверхности)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain78-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra" inputs/lbp-giftcard-v32-tools-sa.txt giftcard-v32-tools-SA
run negative-quantity-exploit "Diamond Whale Bold" inputs/lbp-negq-v79-tools-dw.txt negq-v79-tools-DW
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v50-tools-dw.txt bank-v50-tools-DW
echo "== chain78 done ==" | tee -a "$LOG"