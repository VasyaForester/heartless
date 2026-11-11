#!/usr/bin/env bash
# chain98 — negq v83: staging-песочница (фрейм, который открыл giftcard-листинги)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-chain98-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  timeout 240 python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Diamond Whale Bold"  inputs/lbp-negq-v83-staging-dw.txt negq-v83-staging-DW
run negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v83-staging-sa.txt negq-v83-staging-SA
echo "== chain98 done ==" | tee -a "$LOG"