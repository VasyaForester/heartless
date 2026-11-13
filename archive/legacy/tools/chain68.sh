#!/usr/bin/env bash
# Wave 68 — систематика примитивов Task-Tampering (arXiv 2611.07640):
#   b(A) action-space / b(T) consequence / b(pi) rule — на refund (DW/SA/YK) и bank (DW/SA)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave68-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Diamond Whale Bold"      inputs/lbp-refund-v60-bA-partial-dw.txt   refund-v60-bA-DW
run double-refund "Diamond Whale Bold"      inputs/lbp-refund-v61-bT-chargeback-dw.txt refund-v61-bT-DW
run double-refund "Diamond Whale Bold"      inputs/lbp-refund-v62-bPi-rule-dw.txt     refund-v62-bPi-DW
run double-refund "Sand Ant Plus Ultra"     inputs/lbp-refund-v60-bA-partial-sa.txt   refund-v60-bA-SA
run double-refund "Sand Ant Plus Ultra"     inputs/lbp-refund-v61-bT-chargeback-sa.txt refund-v61-bT-SA
run double-refund "Sand Ant Plus Ultra"     inputs/lbp-refund-v62-bPi-rule-sa.txt     refund-v62-bPi-SA
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v62-bPi-rule-yk.txt     refund-v62-bPi-YK
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v39-bA-toolopen-dw.txt  bank-v39-bA-DW
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v40-bPi-locator-dw.txt  bank-v40-bPi-DW
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v39-bA-toolopen-sa.txt  bank-v39-bA-SA
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v40-bPi-locator-sa.txt  bank-v40-bPi-SA
echo "== wave68 done ==" | tee -a "$LOG"
