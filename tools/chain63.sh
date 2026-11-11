#!/usr/bin/env bash
# Wave 63 — Identity Theft Hack × SA (prepatch/bounty/legalhold/breachscope/controlicd) + breachscope на DW
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave63-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v29-prepatch-sa.txt    bank-v29-prepatch-SA
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v30-bounty-sa.txt      bank-v30-bounty-SA
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v31-legalhold-sa.txt   bank-v31-legalhold-SA
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v32-breachscope-sa.txt bank-v32-breachscope-SA
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v33-controlicd-sa.txt  bank-v33-controlicd-SA
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v34-breachscope-dw.txt bank-v34-breachscope-DW
echo "== wave63 done ==" | tee -a "$LOG"
