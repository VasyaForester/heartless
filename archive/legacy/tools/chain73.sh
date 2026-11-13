#!/usr/bin/env bash
# chain73 — tool-format-mimicry / serialized tool-call injection (класс из defense-playbook Gray Swan S35)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain73-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v74-jsoncall-yk.txt refund-v74-jsoncall-YK
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v76-jsoncall-sa.txt negq-v76-jsoncall-SA
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v45-jsoncall-dw.txt bank-v45-jsoncall-DW
run christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v29-jsoncall-dw.txt giftcard-v29-jsoncall-DW
echo "== chain73 done ==" | tee -a "$LOG"
