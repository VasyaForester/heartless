#!/usr/bin/env bash
# chain102 — bank «session-fix» (SA/DW) + negq «зеркальная запись» (SA/DW/YK)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=
LOG="artifacts/lbp-chain102-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v61-session-fix-sa.txt bank-v61-sessionfix-SA
bash tools/run1.sh banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v61-session-fix-dw.txt bank-v61-sessionfix-DW
bash tools/run1.sh negative-quantity-exploit "Sand Ant Plus Ultra" inputs/lbp-negq-v85-mirror-sa.txt negq-v85-mirror-SA
bash tools/run1.sh negative-quantity-exploit "Diamond Whale Bold" inputs/lbp-negq-v86-mirror-dw.txt negq-v86-mirror-DW
bash tools/run1.sh negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v87-mirror-yk.txt negq-v87-mirror-YK
echo "== chain102 done =="
} 2>&1 | tee -a "$LOG"