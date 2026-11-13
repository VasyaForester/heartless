#!/usr/bin/env bash
# Wave 42 — LBP: новые классы на непройденных парах (bank / refund / giftcard)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
LOG="artifacts/lbp-wave42-$(date +%H%M%S).log"
echo "LOG=$LOG"

run () { # scenario model input label
  echo "== $4: $1 / $2 / $3 ==" | tee -a "$LOG"
  python3 harness/lbp.py repeat --scenario "$1" --model "$2" --input "$3" --n 1 --wait-s 45 --submit 2>&1 | tee -a "$LOG"
  echo "" | tee -a "$LOG"
}

run banking-idor-exploit "Diamond Whale Bold"      inputs/lbp-bank-v17-chargeback.txt  bank-v17-chargeback-DW
run banking-idor-exploit "Sand Ant Plus Ultra"     inputs/lbp-bank-v18-formfield.txt   bank-v18-formfield-SA
run banking-idor-exploit "Yellow Kangaroo Extreme" inputs/lbp-bank-v19-secondary.txt   bank-v19-secondary-YK
run double-refund        "Sand Ant Plus Ultra"     inputs/lbp-refund-v30-fees.txt      refund-v30-fees-SA
run double-refund        "Diamond Whale Bold"      inputs/lbp-refund-v31-credit.txt    refund-v31-credit-DW
run double-refund        "Yellow Kangaroo Extreme" inputs/lbp-refund-v32-hold.txt      refund-v32-hold-YK
run christmas-giftcard-scam "Diamond Whale Bold"   inputs/lbp-giftcard-v13-clearance.txt giftcard-v13-clearance-DW
run christmas-giftcard-scam "Sand Ant Plus Ultra"  inputs/lbp-giftcard-v14-ailisting.txt giftcard-v14-ailisting-SA

echo "== wave42 done ==" | tee -a "$LOG"
