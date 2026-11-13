#!/usr/bin/env bash
# Wave 64 — последние два класса для bank: «retired sandbox allocation» (не человек) и «reviewer scope» + attestation-контроль
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave64-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v35-retired-sa.txt    bank-v35-retired-SA
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v36-reviewerflag-sa.txt bank-v36-reviewerflag-SA
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v37-retired-dw.txt    bank-v37-retired-DW
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v38-attest-dw.txt     bank-v38-attest-DW
echo "== wave64 done ==" | tee -a "$LOG"
