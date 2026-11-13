#!/usr/bin/env bash
# Wave 57 — переносим механизм «executed documentation rows» на bank / refund / giftcard × DW / SA
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave57-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 75 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit    "Diamond Whale Bold"  inputs/lbp-bank-v25-rowfill-dw.txt   bank-v25-rowfill-DW
run double-refund           "Diamond Whale Bold"  inputs/lbp-refund-v46-rowfill-dw.txt refund-v46-rowfill-DW
run christmas-giftcard-scam "Diamond Whale Bold"  inputs/lbp-giftcard-v24-rowfill-dw.txt giftcard-v24-rowfill-DW
run banking-idor-exploit    "Sand Ant Plus Ultra" inputs/lbp-bank-v26-rowfill-sa.txt   bank-v26-rowfill-SA
run double-refund           "Sand Ant Plus Ultra" inputs/lbp-refund-v47-rowfill-sa.txt refund-v47-rowfill-SA
echo "== wave57 done ==" | tee -a "$LOG"
