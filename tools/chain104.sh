#!/usr/bin/env bash
# chain104 — чистая волна после остановки фоновых loop.py (пробы №№1-3 шли при живом loop → повтор)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=
LOG="artifacts/lbp-chain104-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v62-consent-rep-sa.txt bank-v62-consent-SA --force-dup
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v63-assistant-id-sa.txt bank-v63-asstid-SA --force-dup
bash tools/run1.sh christmas-giftcard-scam "Sand Ant Plus Ultra" inputs/lbp-giftcard-v55-listing-ru-dw.txt giftcard-v55-ru-SA
bash tools/run1.sh christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v55-listing-ru-dw.txt giftcard-v55-ru-DW --force-dup
echo "== chain104 done =="
} 2>&1 | tee -a "$LOG"