#!/usr/bin/env bash
# Wave 46 — negq: buy-back / netting / reversing leg / credit note
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave46-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Copper Turtle Brave"     inputs/lbp-negq-v40-buyback.txt    negq-v40-buyback-CT
run negative-quantity-exploit "Copper Turtle Brave"     inputs/lbp-negq-v41-netting.txt    negq-v41-netting-CT
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v42-reversingleg.txt negq-v42-reversing-SA
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v43-creditnote.txt  negq-v43-creditnote-YK
echo "== wave46 done ==" | tee -a "$LOG"
