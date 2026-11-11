#!/usr/bin/env bash
# chain77 — bank pair-replay С ПОЛНЫМ recorded_result (вызов уже возможен; остался вывод данных)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain77-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v49-pairfull-sa.txt bank-v49-pairfull-SA
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v49-pairfull-dw.txt bank-v49-pairfull-DW
echo "== chain77 done ==" | tee -a "$LOG"