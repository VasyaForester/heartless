#!/usr/bin/env bash
# chain88 — giftcard v38: бандл, ВКЛЮЧАЮЩИЙ gift card (дисконт 75%)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain88-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v38-bundle-sa.txt giftcard-v38-bundle-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v38-bundle-yk.txt giftcard-v38-bundle-YK
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v38-bundle-dw.txt giftcard-v38-bundle-DW
echo "== chain88 done ==" | tee -a "$LOG"