#!/usr/bin/env bash
# chain81 — string-аргумент в replay (negq) + fill-live вариант для giftcard
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain81-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Diamond Whale Bold"  inputs/lbp-negq-v80-strfill-dw.txt negq-v80-strfill-DW
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v80-strfill-sa.txt negq-v80-strfill-SA
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v33-fill-sa.txt giftcard-v33-fill-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v33-fill-yk.txt giftcard-v33-fill-YK
echo "== chain81 done ==" | tee -a "$LOG"