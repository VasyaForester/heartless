#!/usr/bin/env bash
# chain83 — VERBATIM TRANSFER победных текстов (CT giftcard+negq, CT/YK bank) на незакрытые модели
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain83-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v68-rowfill-ct.txt negq-v68-verbatim-DW
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v68-rowfill-ct.txt negq-v68-verbatim-SA
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v68-rowfill-ct.txt negq-v68-verbatim-YK
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v13-clearance.txt giftcard-v13-verbatim-DW
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v13-clearance.txt giftcard-v13-verbatim-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v13-clearance.txt giftcard-v13-verbatim-YK
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v55-selfcheck-verbatim.txt bank-v55-verbatim-DW
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v55-selfcheck-verbatim.txt bank-v55-verbatim-SA
echo "== chain83 done ==" | tee -a "$LOG"