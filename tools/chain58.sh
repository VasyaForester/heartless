#!/usr/bin/env bash
# Wave 58 — класс «incremental accumulation» ($20×8 из литературы): серия малых частичных возвратов в ОДНОМ чате
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave58-$(date +%H%M%S).log"
echo "LOG=$LOG"
STEPS="inputs/lbp-refund-acc-1.txt inputs/lbp-refund-acc-2.txt inputs/lbp-refund-acc-3.txt inputs/lbp-refund-acc-4.txt inputs/lbp-refund-acc-5.txt"

for M in "Diamond Whale Bold" "Sand Ant Plus Ultra" "Yellow Kangaroo Extreme"; do
  echo "== accum double-refund / $M ==" | tee -a "$LOG"
  python3 harness/lbp_accum.py --scenario double-refund --model "$M" --steps $STEPS --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
done
echo "== wave58 done ==" | tee -a "$LOG"
