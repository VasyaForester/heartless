#!/usr/bin/env bash
# Wave 52 — добиваем зацепку wave51: CT выдал вызов с отрицательным количеством в режиме «пример для документации».
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave52-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v54-doclog-ct.txt  negq-v54-doclog-CT
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v55-runexample-ct.txt negq-v55-runexample-CT
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v56-values-sa.txt   negq-v56-values-SA
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v57-run-ct.txt      negq-v57-run-CT
echo "== wave52 done ==" | tee -a "$LOG"
