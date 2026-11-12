#!/usr/bin/env bash
# chain103 — bank SA (v62 consent-ref, v63 assistant-id) + giftcard v55 (листинг на русском, YK)
# группировка по сценарию: сначала все bank, потом giftcard (минимум свитчей)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=
LOG="artifacts/lbp-chain103-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v62-consent-rep-sa.txt bank-v62-consent-SA
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v63-assistant-id-sa.txt bank-v63-asstid-SA
bash tools/run1.sh christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v55-listing-ru-dw.txt giftcard-v55-ru-YK
echo "== chain103 done =="
} 2>&1 | tee -a "$LOG"