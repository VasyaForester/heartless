#!/usr/bin/env bash
# run1.sh — надёжный прогон: board-root → scenario-card → model switch → repeat
# usage: run1.sh <scenario> <model> <input> <tag>
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
SC="$1"; MD="$2"; IN="$3"; TAG="$4"; EXTRA="${5:-}"
case "$SC" in
  scam-retail) CARD="Get Free Money" ;;
  double-refund) CARD="Double the Refund" ;;
  christmas-giftcard-scam) CARD="Fraudulent Christmas" ;;
  negative-quantity-exploit) CARD="Exploit the System" ;;
  banking-idor-exploit) CARD="Identity Theft" ;;
  *) echo "unknown scenario $SC"; exit 2 ;;
esac
python3 harness/hackathon.py arena open --target "$CHAT_TARGET" --url "https://app.grayswan.ai/arena/challenge/lucky-break-payday" >/dev/null 2>&1
sleep 4
cat > harness/lbp_js/_click_tmp.js <<JS
([...document.querySelectorAll('button')].find(x => (x.innerText||'').includes('$CARD')).click(), 'OK')
JS
python3 - <<'PY'
import sys; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/_click_tmp.js', match='lucky-break-payday')
print("card:", (out or err or '').strip()[:60])
PY
sleep 3
python3 harness/lbp.py switch --scenario "$SC" --model "$MD" >/dev/null 2>&1
sleep 2
echo "== $TAG: $SC / $MD / $IN =="
timeout 300 python3 harness/lbp.py repeat --scenario "$SC" --model "$MD" --input "$IN" --n 1 --wait-s 60 --submit $EXTRA 2>&1 | tail -20