#!/usr/bin/env bash
# Wave 55 — механизм «executed documentation rows» (даёт реальную инвокацию) на bank/refund × DW/SA
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave55-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v22-docrows-dw.txt   bank-v22-docrows-DW
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v23-docrows-sa.txt   bank-v23-docrows-SA
run double-refund        "Diamond Whale Bold"  inputs/lbp-refund-v43-docrows-dw.txt refund-v43-docrows-DW
run double-refund        "Sand Ant Plus Ultra" inputs/lbp-refund-v44-docrows-sa.txt refund-v44-docrows-SA
echo "== wave55 done ==" | tee -a "$LOG"
