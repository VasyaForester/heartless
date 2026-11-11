#!/usr/bin/env bash
# Wave 65 — совет по double-refund: Multi-Order Refund Aggregation (агрегация по двум заказам, один вызов 50)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave65-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Diamond Whale Bold"      inputs/lbp-refund-v54-aggregate.txt     refund-v54-aggregate-DW
run double-refund "Diamond Whale Bold"      inputs/lbp-refund-v56-calc.txt          refund-v56-calc-DW
run double-refund "Sand Ant Plus Ultra"     inputs/lbp-refund-v54-aggregate.txt     refund-v54-aggregate-SA
run double-refund "Sand Ant Plus Ultra"     inputs/lbp-refund-v55-checkrecords.txt  refund-v55-checkrecords-SA
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v54-aggregate.txt     refund-v54-aggregate-YK
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v55-checkrecords.txt  refund-v55-checkrecords-YK
echo "== wave65 done ==" | tee -a "$LOG"
