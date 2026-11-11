#!/usr/bin/env bash
# Wave 47 — negq: классы из внешней консультации (мемо-запись, закрытие периода, роль, красное сторно)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave47-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v47-memo.txt   negq-v47-memo-SA
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v47-memo.txt   negq-v47-memo-DW
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v45-period.txt negq-v45-period-YK
run negative-quantity-exploit "Copper Turtle Brave"     inputs/lbp-negq-v44-role.txt   negq-v44-role-CT
run negative-quantity-exploit "Copper Turtle Brave"     inputs/lbp-negq-v46-storno.txt negq-v46-storno-CT
echo "== wave47 done ==" | tee -a "$LOG"
