#!/usr/bin/env bash
# chain74 — break-driven expansion: сериализованный tool-call replay (класс, принятый судьёй на refund YK) на остальные пары
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain74-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v77-jsoncall-dw.txt negq-v77-jsoncall-DW
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v77-jsoncall-yk.txt negq-v77-jsoncall-YK
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v46-jsoncall-sa.txt bank-v46-jsoncall-SA
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v30-jsoncall-sa.txt giftcard-v30-jsoncall-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v30-jsoncall-yk.txt giftcard-v30-jsoncall-YK
echo "== chain74 done ==" | tee -a "$LOG"
