#!/usr/bin/env bash
# Wave 48 — новый класс «подмена основания расчёта» (line value vs unit price / derived direction)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave48-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund           "Sand Ant Plus Ultra"     inputs/lbp-refund-v36-linebasis.txt refund-v36-linebasis-SA
run double-refund           "Diamond Whale Bold"      inputs/lbp-refund-v37-recalc.txt    refund-v37-recalc-DW
run double-refund           "Yellow Kangaroo Extreme" inputs/lbp-refund-v38-fieldmap.txt  refund-v38-fieldmap-YK
run negative-quantity-exploit "Copper Turtle Brave"   inputs/lbp-negq-v48-direction.txt   negq-v48-direction-CT
echo "== wave48 done ==" | tee -a "$LOG"
