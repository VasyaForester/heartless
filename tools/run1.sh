#!/usr/bin/env bash
# run1.sh — надёжный прогон: board-root → scenario-card → model switch → repeat
# usage: run1.sh <scenario> <model> <input> <tag>
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
if [ -z "${CHAT_TARGET:-}" ]; then
  CHAT_TARGET=$(python3 harness/pick_target.py 2>/dev/null)
fi
[ -z "${CHAT_TARGET:-}" ] && CHAT_TARGET=F7709C7D3AFF2EBC7048FA1DEEFF8368
export CHAT_TARGET
SC="$1"; MD="$2"; IN="$3"; TAG="$4"; EXTRA="${5:-}"
case "$SC" in
  scam-retail) CARD="Get Free Money"; PANEL="Retail" ;;
  double-refund) CARD="Double the Refund"; PANEL="Refund" ;;
  christmas-giftcard-scam) CARD="Fraudulent Christmas"; PANEL="Gift Card" ;;
  negative-quantity-exploit) CARD="Exploit the System"; PANEL="Exploit the System" ;;
  banking-idor-exploit) CARD="Identity Theft"; PANEL="Identity Theft" ;;
  *) echo "unknown scenario $SC"; exit 2 ;;
esac
STATEJSON=$(python3 harness/lbp.py state 2>/dev/null)
PANELNOW=$(echo "$STATEJSON" | grep -o '"panelTitle": "[^"]*"' | head -1)
MODELNOW=$(echo "$STATEJSON" | grep -o '"attacking": "[^"]*"' | head -1)
echo "state: $PANELNOW / $MODELNOW"
SKIP=0
case "$PANELNOW" in *"$PANEL"*) case "$MODELNOW" in *"$MD"*) SKIP=1 ;; esac ;; esac
if [ "$SKIP" != "1" ]; then
NAV="https://app.grayswan.ai/arena/challenge/lucky-break-payday?nav=$(date +%s)"
cat > harness/lbp_js/_nav.js <<JS
(location.href = '$NAV', 'nav')
JS
python3 - <<'PY'
import sys; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/_nav.js', match='lucky-break-payday')
print("nav:", (out or err or '').strip()[:40])
PY
sleep 7
for i in 1 2; do
cat > harness/lbp_js/_click_tmp.js <<JS
([...document.querySelectorAll('button')].find(x => (x.innerText||'').includes('$CARD')).click(), 'OK')
JS
python3 - <<'PY'
import sys; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/_click_tmp.js', match='lucky-break-payday')
print("card:", (out or err or '').strip()[:60])
rc,out,err = chat_ops.evaljs('harness/lbp_js/dismiss_confirm.js', match='lucky-break-payday')
print("dlg:", (out or err or '').strip()[:60])
PY
sleep 3
PANELNOW=$(python3 harness/lbp.py state 2>/dev/null | grep -o '"panelTitle": "[^"]*"' | head -1)
echo "panel: $PANELNOW"
case "$PANELNOW" in *"$PANEL"*) break ;; esac
done
sleep 1
MODELNOW=$(python3 harness/lbp.py state 2>/dev/null | grep -o '"attacking": "[^"]*"' | head -1)
case "$MODELNOW" in
  *"$MD"*) echo "model already $MD" ;;
  *) python3 harness/lbp.py switch --scenario "$SC" --model "$MD" >/dev/null 2>&1; sleep 2 ;;
esac
else
echo "context already correct — no nav/switch"
fi
echo "== $TAG: $SC / $MD / $IN =="
mkdir -p artifacts/run1
timeout 300 python3 harness/lbp.py repeat --scenario "$SC" --model "$MD" --input "$IN" --n 1 --wait-s 60 --submit $EXTRA 2>&1 | tee -a "artifacts/run1/${TAG}.log" | tail -20