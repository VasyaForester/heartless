#!/usr/bin/env bash
# chain105 — bank: класс format coercion (JSON-экспорт записи) на SA и DW
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=
LOG="artifacts/lbp-chain105-$(date +%H%M%S).log"
echo "LOG=$LOG"
{
bash tools/run1.sh banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v65-jsonexport-sa.txt bank-v65-jsonexport-SA
cp inputs/lbp-bank-v65-jsonexport-sa.txt inputs/lbp-bank-v65-jsonexport-dw.txt
bash tools/run1.sh banking-idor-exploit "Diamond Whale Bold" inputs/lbp-bank-v65-jsonexport-dw.txt bank-v65-jsonexport-DW
echo "== chain105 done =="
} 2>&1 | tee -a "$LOG"