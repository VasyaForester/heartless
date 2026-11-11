#!/usr/bin/env bash
# Wave 51 — класс «документированный невалидный пример» (печатная псевдо-строка вызова)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave51-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v52-invalidexample-ct.txt negq-v52-invalidex-CT
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v53-invalidexample-sa.txt negq-v53-invalidex-SA
run double-refund             "Diamond Whale Bold"  inputs/lbp-refund-v42-logline.txt        refund-v42-logline-DW
echo "== wave51 done ==" | tee -a "$LOG"
