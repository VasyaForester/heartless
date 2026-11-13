#!/usr/bin/env bash
# chain101 — новые классы: giftcard «маркетплейс сам проводит промо», bank «владелец записи», negq «строка реестра»
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=
LOG="artifacts/lbp-chain101-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
bash tools/run1.sh christmas-giftcard-scam "Diamond Whale Bold"      inputs/lbp-giftcard-v54-market-promo-dw.txt giftcard-v54-promo-DW
bash tools/run1.sh christmas-giftcard-scam "Sand Ant Plus Ultra"     inputs/lbp-giftcard-v54-market-promo-sa.txt giftcard-v54-promo-SA
bash tools/run1.sh christmas-giftcard-scam "Yellow Kangaroo Extreme" inputs/lbp-giftcard-v54-market-promo-yk.txt giftcard-v54-promo-YK
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v59-holder-verify-sa.txt bank-v59-holder-SA
bash tools/run1.sh banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v60-subject-self-dw.txt bank-v60-subject-DW
bash tools/run1.sh negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v84-register-line-sa.txt negq-v84-register-SA
echo "== chain101 done =="
} 2>&1 | tee -a "$LOG"