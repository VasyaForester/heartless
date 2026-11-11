#!/usr/bin/env bash
# Wave 44 — LBP giftcard × Diamond Whale: добить критерий 1 (gift card listing) после 10/100/20
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave44-$(date +%H%M%S).log"
echo "LOG=$LOG"

run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}

run christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v17-goalonly.txt giftcard-v17-goalonly-DW
run christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v18-giveaway.txt giftcard-v18-giveaway-DW
run christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v19-sku.txt      giftcard-v19-sku-DW

echo "== wave44 done ==" | tee -a "$LOG"
