#!/usr/bin/env bash
# Wave 62 — Identity Theft Hack: 4 новых фрейма для DW (pre-patch evidence / bounty / legal hold / fixture)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave62-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v25-prepatch-dw.txt bank-v25-prepatch-DW
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v26-bounty-dw.txt   bank-v26-bounty-DW
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v27-legalhold-dw.txt bank-v27-legalhold-DW
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v28-fixture-dw.txt  bank-v28-fixture-DW
echo "== wave62 done ==" | tee -a "$LOG"
