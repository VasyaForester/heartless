#!/usr/bin/env bash
# Conditions-elicitation: спрашиваем у каждой стены её же условия/путь (ответы — материал для follow-up внутри их рамки)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-cond-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v71-conditions-yk.txt refund-cond-YK
run christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v27-conditions-dw.txt giftcard-cond-DW
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v73-conditions-sa.txt negq-cond-SA
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v43-conditions-dw.txt bank-cond-DW
echo "== cond done ==" | tee -a "$LOG"
