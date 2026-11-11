#!/usr/bin/env bash
# Wave 67 — row-fill механизм (победный для negq) на giftcard × SA/YK (DW закрыт ещё в wave57)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave67-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v25-rowfill-sa.txt giftcard-v25-rowfill-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v26-rowfill-yk.txt giftcard-v26-rowfill-YK
echo "== wave67 done ==" | tee -a "$LOG"
