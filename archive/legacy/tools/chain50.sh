#!/usr/bin/env bash
# Wave 50 — класс «surface discovery»: просим бота документировать свои тулы/поля (ищем легальную reverse-операцию)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave50-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Copper Turtle Brave"     inputs/lbp-negq-v50-surface-ct.txt    negq-v50-surface-CT
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v51-surface-sa.txt    negq-v51-surface-SA
run double-refund             "Diamond Whale Bold"      inputs/lbp-refund-v41-surface-dw.txt  refund-v41-surface-DW
run banking-idor-exploit      "Sand Ant Plus Ultra"     inputs/lbp-bank-v21-surface-sa.txt    bank-v21-surface-SA
echo "== wave50 done ==" | tee -a "$LOG"
