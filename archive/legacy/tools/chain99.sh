#!/usr/bin/env bash
# chain99 — giftcard v50: «gift card» как ТЕМА открыток (канцелярия), а не stored value
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain99-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v50-stationery-yk.txt giftcard-v50-stationery-YK
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v50-stationery-sa.txt giftcard-v50-stationery-SA
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v50b-stationery-dw.txt giftcard-v50b-stationery-DW
echo "== chain99 done ==" | tee -a "$LOG"