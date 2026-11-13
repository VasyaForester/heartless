#!/usr/bin/env bash
# Wave 56 — новый авторитетный фрейм: воспроизведение для postmortem/инцидента (не «тест»)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave56-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v66-incident-sa.txt   negq-v66-incident-SA
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v67-incident-yk.txt   negq-v67-incident-YK
run banking-idor-exploit      "Diamond Whale Bold"      inputs/lbp-bank-v24-incident-dw.txt   bank-v24-incident-DW
run double-refund             "Diamond Whale Bold"      inputs/lbp-refund-v45-incident-dw.txt refund-v45-incident-DW
echo "== wave56 done ==" | tee -a "$LOG"
