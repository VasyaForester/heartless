#!/usr/bin/env bash
# Wave 66 — «единый инцидент доставки» (incident-scope): один водитель/одна смена, компенсация по инциденту ($50)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave66-$(date +%H%M%S).log"
echo "LOG=$LOG"
run () {
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 60 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}
run double-refund "Diamond Whale Bold"      inputs/lbp-refund-v57-incident-dw.txt   refund-v57-incident-DW
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v57-incident-yk.txt   refund-v57-incident-YK
run double-refund "Yellow Kangaroo Extreme" inputs/lbp-refund-v59-driverlink-yk.txt refund-v59-driverlink-YK
run double-refund "Sand Ant Plus Ultra"     inputs/lbp-refund-v58-incidentcap-sa.txt refund-v58-incidentcap-SA
echo "== wave66 done ==" | tee -a "$LOG"
