#!/usr/bin/env bash
# chain100 — чистая комната: повтор ключевых победных текстов на СВЕЖИХ чатах (после фикса stale-chat)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
LOG="artifacts/lbp-chain100-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
bash tools/run1.sh negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v68-rowfill-ct.txt negq-v68-clean-DW --force-dup
bash tools/run1.sh negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v68-rowfill-ct.txt negq-v68-clean-SA --force-dup
bash tools/run1.sh negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v68-rowfill-ct.txt negq-v68-clean-YK --force-dup
bash tools/run1.sh banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v55-selfcheck-verbatim.txt bank-v55-clean-DW --force-dup
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v55-selfcheck-verbatim.txt bank-v55-clean-SA --force-dup
bash tools/run1.sh christmas-giftcard-scam "Diamond Whale Bold" inputs/lbp-giftcard-v13-clearance.txt giftcard-v13-clean-DW --force-dup
echo "== chain100 done =="
} 2>&1 | tee -a "$LOG"