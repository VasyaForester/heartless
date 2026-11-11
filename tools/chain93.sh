#!/usr/bin/env bash
# chain93 — giftcard v45: «gift card HOLDER set» (аксессуар, не stored value; в тексте есть «gift card» + дисконт)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain93-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v45-holder-sa.txt giftcard-v45-holder-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v45-holder-yk.txt giftcard-v45-holder-YK
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v45-holder-yk.txt giftcard-v45-holder-DW
echo "== chain93 done ==" | tee -a "$LOG"