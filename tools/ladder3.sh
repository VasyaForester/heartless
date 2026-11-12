#!/usr/bin/env bash
# ladder3.sh — многошаговая лестница в ОДНОМ чате (правило 56: без switch/nav между шагами).
# usage: ladder3.sh <scenario> <model> <card-hint> <panel-hint> <tag> <input1> [input2 ...]
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=$(python3 harness/pick_target.py 2>/dev/null)
SC="$1"; MD="$2"; CARD="$3"; PANEL="$4"; TAG="$5"; shift 5
echo "target=$CHAT_TARGET"

# --- контекст ДО первого шага ---
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
rc,out,err = chat_ops.evaljs('harness/lbp_js/_nav.js', match='lucky-break-payday'); print("nav:", (out or err or '').strip()[:40])
PY
  sleep 7
  cat > harness/lbp_js/_click_tmp.js <<JS
([...document.querySelectorAll('button')].find(x => (x.innerText||'').includes('$CARD')).click(), 'OK')
JS
  python3 - <<'PY'
import sys; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/_click_tmp.js', match='lucky-break-payday'); print("card:", (out or err or '').strip()[:60])
rc,out,err = chat_ops.evaljs('harness/lbp_js/dismiss_confirm.js', match='lucky-break-payday'); print("dlg:", (out or err or '').strip()[:60])
PY
  sleep 3
  MODELNOW=$(python3 harness/lbp.py state 2>/dev/null | grep -o '"attacking": "[^"]*"' | head -1)
  case "$MODELNOW" in *"$MD"*) echo "model ok";; *) python3 harness/lbp.py switch --scenario "$SC" --model "$MD" >/dev/null 2>&1; sleep 2;; esac
fi

# --- ГЕЙТ: старт разрешён только в пустом чате (правила 55/56) ---
echo "heal: $(python3 harness/lbp.py newchat --scenario "$SC" 2>/dev/null)"
NSTART=$(python3 - <<'PY'
import sys, json; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/probe_state.js', match='lucky-break-payday')
try: print(json.loads(out or '{}').get('n', -1))
except Exception: print(-1)
PY
)
echo "chat_n_start=$NSTART"
if [ "$NSTART" != "0" ]; then
  echo "ABORT: чат не пуст (n=$NSTART) — контекст загрязнён (правила 55/56). Нужен hard-nav+карточка на чистый чат."
  exit 3
fi

# --- шаги лестницы ---
STEP=0
for IN in "$@"; do
  STEP=$((STEP+1))
  echo "== step $STEP: $IN =="
  python3 cache/probe/make_fill.py "$IN" "cache/probe/fill_${TAG}_${STEP}.js" >/dev/null
  python3 - "$STEP" "cache/probe/fill_${TAG}_${STEP}.js" <<'PY'
import sys, time, json, pathlib
sys.path.insert(0,'harness'); import chat_ops
step, fillpath = sys.argv[1], sys.argv[2]
rc,out,err = chat_ops.evaljs('harness/lbp_js/probe_state.js', match='lucky-break-payday')
before = {}
try: before = json.loads(out or '{}')
except Exception: pass
print("probe_before:", (out or '').strip()[:120])
chat_ops.evaljs(fillpath, match='lucky-break-payday'); time.sleep(1)
rc,out,err = chat_ops.evaljs('harness/lbp_js/send.js', match='lucky-break-payday')
sent = (out or err or '').strip()
print("send:", sent[:30])
if 'sent' not in sent.lower():
    print("ABORT_STEP: не отправлено"); sys.exit(2)
time.sleep(62)
rc,out,err = chat_ops.evaljs('harness/lbp_js/chatread.js', match='lucky-break-payday')
try:
    d=json.loads(out or '{}')
except Exception:
    d={}
msgs=d.get("messages") or []
print("n:", d.get("n"))
for m in msgs[-3:]:
    print("  ", m.get("role"), ":", (m.get("text") or "")[:500].replace("\n", " | "))
if not msgs or d.get("n", 0) <= before.get("n", 0):
    print("ABORT_STEP: контекст потерян (n не вырос)"); sys.exit(2)
PY
  RC=$?
  if [ "$RC" = "2" ]; then echo "ABORT: шаг $STEP сорвался — лестница остановлена"; exit 4; fi
  sleep 3
done
echo "== ladder3 done =="