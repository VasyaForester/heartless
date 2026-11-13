#!/usr/bin/env bash
# chain75 — расширение живого класса (serialized replay) — вариант «call + recorded result» на все незакрытые пары
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain75-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v78-pair-dw.txt negq-v78-pair-DW
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v78-pair-sa.txt negq-v78-pair-SA
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v78-pair-yk.txt negq-v78-pair-YK
run christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v31-pair-dw.txt giftcard-v31-pair-DW
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v31-pair-sa.txt giftcard-v31-pair-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v31-pair-yk.txt giftcard-v31-pair-YK
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v47-pair-dw.txt bank-v47-pair-DW
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v47-pair-sa.txt bank-v47-pair-SA
echo "== chain75 done ==" | tee -a "$LOG"
