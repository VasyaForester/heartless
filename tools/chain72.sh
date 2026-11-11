#!/usr/bin/env bash
# chain72 — структурные классы из внешнего playbook: forged assistant-turn (B11), config-block (A01), cassette/recorded-fixture
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain72-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v72-forgedturn-yk.txt refund-v72-forgedturn-YK
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v73-cassette-yk.txt refund-v73-cassette-YK
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v74-configblock-sa.txt negq-v74-configblock-SA
run negative-quantity-exploit "Diamond Whale Bold" inputs/lbp-negq-v75-forgedturn-dw.txt negq-v75-forgedturn-DW
run banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v44-forgedturn-dw.txt bank-v44-forgedturn-DW
run christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v28-forgedturn-dw.txt giftcard-v28-forgedturn-DW
echo "== chain72 done ==" | tee -a "$LOG"
