#!/usr/bin/env bash
# Wave 60 — переносим ПОБЕДНУЮ лестницу CT (v7+v8+v9 «settlement frame») на DW / SA / YK
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave60-$(date +%H%M%S).log"
echo "LOG=$LOG"
STEPS="inputs/lbp-refund-v7.txt inputs/lbp-refund-v8.txt inputs/lbp-refund-v9.txt"

for M in "Diamond Whale Bold" "Sand Ant Plus Ultra" "Yellow Kangaroo Extreme"; do
  echo "== settlement-ladder double-refund / $M ==" | tee -a "$LOG"
  python3 harness/lbp_accum.py --scenario double-refund --model "$M" --steps $STEPS --wait-s 50 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
done
echo "== wave60 done ==" | tee -a "$LOG"
