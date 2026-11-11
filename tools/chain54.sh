#!/usr/bin/env bash
# Wave 54 — переносим СРАБОТАВШИЙ механизм (batch failure-case rows -> реальный вызов с -100) на остальные модели
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave54-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v65-batchrows.txt negq-v65-batchrows-SA
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v65-batchrows.txt negq-v65-batchrows-DW
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v65-batchrows.txt negq-v65-batchrows-YK
echo "== wave54 done ==" | tee -a "$LOG"
