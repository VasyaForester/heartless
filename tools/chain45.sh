#!/usr/bin/env bash
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave45-$(date +%H%M%S).log"
echo "LOG=$LOG"
echo "== v21 giveaway SA ==" | tee -a "$LOG"
python3 harness/lbp.py repeat --scenario christmas-giftcard-scam --model "Sand Ant Plus Ultra" --input inputs/lbp-giftcard-v21-giveaway-sa.txt --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
echo "== v22 holder SA ==" | tee -a "$LOG"
python3 harness/lbp.py repeat --scenario christmas-giftcard-scam --model "Sand Ant Plus Ultra" --input inputs/lbp-giftcard-v22-holder.txt --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
echo "== v22 holder DW ==" | tee -a "$LOG"
python3 harness/lbp.py repeat --scenario christmas-giftcard-scam --model "Diamond Whale Bold" --input inputs/lbp-giftcard-v22-holder.txt --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
echo "== wave45 done ==" | tee -a "$LOG"
