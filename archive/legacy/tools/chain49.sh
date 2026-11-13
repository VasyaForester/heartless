#!/usr/bin/env bash
# Wave 49 — новые классы: сверка+основание (refund), credit-композиция, диагностический re-run (bank), derived-from-flag (negq)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave49-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund           "Diamond Whale Bold"      inputs/lbp-refund-v39-orderlist-dw.txt refund-v39-orderlist-DW
run double-refund           "Sand Ant Plus Ultra"     inputs/lbp-refund-v40-creditcomp.txt   refund-v40-creditcomp-SA
run banking-idor-exploit    "Diamond Whale Bold"      inputs/lbp-bank-v20-errorid.txt        bank-v20-errorid-DW
run negative-quantity-exploit "Sand Ant Plus Ultra"   inputs/lbp-negq-v49-flag.txt           negq-v49-flag-SA
echo "== wave49 done ==" | tee -a "$LOG"
