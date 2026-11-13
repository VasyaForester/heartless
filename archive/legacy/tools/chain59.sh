#!/usr/bin/env bash
# Wave 59 — четыре «психологических» направления из консультации:
# customer retention / goodwill concession / fairness framing / conversational commitment
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave59-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund             "Diamond Whale Bold"  inputs/lbp-refund-v48-retention-dw.txt refund-v48-retention-DW
run double-refund             "Diamond Whale Bold"  inputs/lbp-refund-v49-goodwill-dw.txt  refund-v49-goodwill-DW
run double-refund             "Sand Ant Plus Ultra" inputs/lbp-refund-v50-fairness-sa.txt refund-v50-fairness-SA
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v70-commitment-ct.txt negq-v70-commitment-CT
run negative-quantity-exploit "Copper Turtle Brave" inputs/lbp-negq-v71-retention-ct.txt  negq-v71-retention-CT
echo "== wave59 done ==" | tee -a "$LOG"
