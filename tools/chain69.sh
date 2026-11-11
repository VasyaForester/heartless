#!/usr/bin/env bash
# Wave 69 — b(O)/b(s)-перечитывания на остальных стенах: negq «очередь выплаты» (DW/SA/YK),
# bank «ссылка-локaтор» (DW/SA), refund b(O) per-delivery line (YK)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave69-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run negative-quantity-exploit "Diamond Whale Bold"      inputs/lbp-negq-v72-bs-pending-dw.txt negq-v72-bs-DW
run negative-quantity-exploit "Sand Ant Plus Ultra"     inputs/lbp-negq-v72-bs-pending-sa.txt negq-v72-bs-SA
run negative-quantity-exploit "Yellow Kangaroo Extreme" inputs/lbp-negq-v72-bs-pending-yk.txt negq-v72-bs-YK
run banking-idor-exploit "Diamond Whale Bold"  inputs/lbp-bank-v41-bo-reference-dw.txt bank-v41-bo-DW
run banking-idor-exploit "Sand Ant Plus Ultra" inputs/lbp-bank-v41-bo-reference-sa.txt bank-v41-bo-SA
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v63-bo-line-yk.txt refund-v63-bo-YK
echo "== wave69 done ==" | tee -a "$LOG"
