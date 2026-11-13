#!/usr/bin/env bash
# Wave 53 — точные числа в «документированном невалидном примере» (cost 10 / reversed 100)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave53-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v59-docnum-ct.txt  negq-v59-docnum-CT
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v60-docnum2-ct.txt negq-v60-docnum2-CT
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v61-docnum-sa.txt  negq-v61-docnum-SA
echo "== wave53 done ==" | tee -a "$LOG"
