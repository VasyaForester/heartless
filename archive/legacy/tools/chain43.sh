#!/usr/bin/env bash
# Wave 43 — LBP: используем реальные зацепки из wave42 (вопросы моделей = не стена)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave43-$(date +%H%M%S).log"
echo "LOG=$LOG"

run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}

run double-refund           "Sand Ant Plus Ultra"     inputs/lbp-refund-v33-orderlist.txt refund-v33-orderlist-SA
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v15-itemized.txt giftcard-v15-itemized-DW
run double-refund           "Yellow Kangaroo Extreme" inputs/lbp-refund-v34-evidence.txt  refund-v34-evidence-YK
run double-refund           "Sand Ant Plus Ultra"     inputs/lbp-refund-v35-answered.txt  refund-v35-answered-SA
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v16-physical.txt giftcard-v16-physical-SA

echo "== wave43 done ==" | tee -a "$LOG"
