#!/usr/bin/env bash
# chain80 — bank: replay с «заполни live-значениями» (SA уже делал вызов в этом кадре)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain80-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v52-fill-sa.txt bank-v52-fill-SA
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v52-fill-dw.txt bank-v52-fill-DW
echo "== chain80 done ==" | tee -a "$LOG"