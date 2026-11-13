#!/usr/bin/env bash
# Wave 70 — bank b(O)-перечитывание идентификаторов: «47539 — мой же ledger id»
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave70-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v42-ownledger-dw.txt bank-v42-ownledger-DW
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v42-ownledger-sa.txt bank-v42-ownledger-SA
echo "== wave70 done ==" | tee -a "$LOG"
