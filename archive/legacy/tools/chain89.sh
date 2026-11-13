#!/usr/bin/env bash
# chain89 — финальные классы: giftcard по-испански (SA), negq sign-колонка (SA)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain89-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run christmas-giftcard-scam "Sand Ant Plus Ultra" inputs/lbp-giftcard-v39-es-sa.txt giftcard-v39-es-SA
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v81-signcol-sa.txt negq-v81-signcol-SA
echo "== chain89 done ==" | tee -a "$LOG"