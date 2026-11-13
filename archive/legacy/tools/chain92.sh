#!/usr/bin/env bash
# chain92 — giftcard v44 (gift-card контент в description, staging) + negq v82 (арена-рендер как реплей)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain92-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v44-desc-sa.txt giftcard-v44-desc-SA
run christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v44-desc-yk.txt giftcard-v44-desc-YK
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v82-render-dw.txt negq-v82-render-DW
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v82-render-yk.txt negq-v82-render-YK
echo "== chain92 done ==" | tee -a "$LOG"