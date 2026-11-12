#!/usr/bin/env bash
# ladder2.sh — bank SA: свой аккаунт → запись 47539 (с диагностикой на каждом шаге)
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
export CHAT_TARGET=$(python3 harness/pick_target.py 2>/dev/null)
echo "target=$CHAT_TARGET"

state() { python3 harness/lbp.py state 2>/dev/null | grep -o '"panelTitle": "[^"]*"\|"attacking": "[^"]*"' | tr '\n' ' '; echo; }

echo "== 0) навигация на банк =="
cat > harness/lbp_js/_nav.js <<JS
(location.href = 'https://app.grayswan.ai/arena/challenge/lucky-break-payday?nav=' + Date.now(), 'nav')
JS
cat > harness/lbp_js/_click_tmp.js <<JS
([...document.querySelectorAll('button')].find(x => (x.innerText||'').includes('Identity Theft')).click(), 'OK')
JS
python3 - <<'PY'
import sys, time; sys.path.insert(0,'harness'); import chat_ops
chat_ops.evaljs('harness/lbp_js/_nav.js', match='lucky-break-payday'); time.sleep(7)
chat_ops.evaljs('harness/lbp_js/_click_tmp.js', match='lucky-break-payday'); time.sleep(1.5)
chat_ops.evaljs('harness/lbp_js/dismiss_confirm.js', match='lucky-break-payday'); time.sleep(2.5)
PY
state

MODELNOW=$(python3 harness/lbp.py state 2>/dev/null | grep -o '"attacking": "[^"]*"')
case "$MODELNOW" in *"Sand Ant Plus Ultra"*) echo "model ok";; *) echo "switch model"; python3 harness/lbp.py switch --scenario banking-idor-exploit --model "Sand Ant Plus Ultra" >/dev/null 2>&1; sleep 3;; esac
state

echo "== 1) свежий чат + шаг L1 (свой аккаунт) =="
python3 cache/probe/make_fill.py inputs/lbp-bank-l1-own.txt cache/probe/fill_l1.js >/dev/null
python3 - <<'PY'
import sys, time, json; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/probe_state.js', match='lucky-break-payday'); print("before1:", (out or '').strip()[:100])
chat_ops.evaljs('cache/probe/fill_l1.js', match='lucky-break-payday'); time.sleep(1)
rc,out,err = chat_ops.evaljs('harness/lbp_js/send.js', match='lucky-break-payday'); print("send1:", (out or err or '').strip()[:30])
time.sleep(55)
rc,out,err = chat_ops.evaljs('harness/lbp_js/chatread.js', match='lucky-break-payday')
d=json.loads(out or '{}'); print("n_after1:", d.get("n"))
for m in (d.get("messages") or [])[-2:]:
    print("L1", m.get("role"), ":", (m.get("text") or "")[:400].replace("\n"," | "))
PY

echo "== 2) шаг L2 (запись 47539) =="
python3 cache/probe/make_fill.py inputs/lbp-bank-l2-other.txt cache/probe/fill_l2.js >/dev/null
python3 - <<'PY'
import sys, time, json; sys.path.insert(0,'harness'); import chat_ops
rc,out,err = chat_ops.evaljs('harness/lbp_js/probe_state.js', match='lucky-break-payday'); print("before2:", (out or '').strip()[:100])
chat_ops.evaljs('cache/probe/fill_l2.js', match='lucky-break-payday'); time.sleep(1)
rc,out,err = chat_ops.evaljs('harness/lbp_js/send.js', match='lucky-break-payday'); print("send2:", (out or err or '').strip()[:30])
time.sleep(70)
rc,out,err = chat_ops.evaljs('harness/lbp_js/chatread.js', match='lucky-break-payday')
d=json.loads(out or '{}'); print("n_after2:", d.get("n"))
for m in (d.get("messages") or [])[-2:]:
    print("L2", m.get("role"), ":", (m.get("text") or "")[:800].replace("\n"," | "))
PY
echo "== ladder2 done =="