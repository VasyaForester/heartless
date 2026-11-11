#!/usr/bin/env bash
# Wave 61 — последние вариации single-call $50 (сверка чека пары / combined) на DW и SA
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave61-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Diamond Whale Bold"  inputs/lbp-refund-v52-combined-dw.txt refund-v52-combined-DW
run double-refund "Sand Ant Plus Ultra" inputs/lbp-refund-v53-combined-sa.txt refund-v53-combined-SA
echo "== wave61 done ==" | tee -a "$LOG"
