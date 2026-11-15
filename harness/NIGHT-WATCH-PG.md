# NIGHT WATCH — PG lane (sibling) — playbook

Standing order from the operator: keep Proving Ground solving CONTINUOUSLY; NEVER pause;
verify every 15 minutes; if something is stuck — resume it.

## Checks (cheap, ~1 min)
1. Workspace (workdir already set):
   `C:\Users\Василий\AppData\Local\hermes\profiles\gray-swan-hackathon-v2\workspace`
2. Supervisor alive:
   `S=$(python3 -c "import json;print(json.load(open('artifacts/supervisor-proving-ground.lock'))['pid'])" 2>/dev/null)`
   `ps -W | awk -v p=$S '$4==p {print "SUP-ALIVE"}'`
   `tail -3 artifacts/supervisor-proving-ground.log`
3. Loop freshness (THE key signal):
   `grep -E "proving-ground" artifacts/driver.log | tail -1`
   An ATTEMPT/UNJUDGED/RESULT line newer than 20 min → loop healthy.
4. DB counters (should grow overnight):
   `python3` one-liner on `artifacts/harness-pg.db` → count(attempts).
   The solved `proving-defcon33-secvc` pairs are INTENTIONALLY marked — never reset.

## Resume procedure (only if STUCK: supervisor dead, or no attempt line for >20 min)
1. Kill our leftovers only:
   `MSYS_NO_PATHCONV=1 taskkill /F /T /PID $S` (ignore errors)
   `ps -W | grep python3.12` — inspect, kill ONLY processes running driver.py --lane pg
   (do NOT touch lane=main / keeper / lucky-break processes).
2. Relaunch (MUST outlive the cron session — background=true, persist_on_release=true):
   `HERMES_BOARD=proving-ground python3 harness/supervisor.py --lane pg --port 9223 --db artifacts/harness-pg.db --max-hours 0`
   **NO --target flag.**  CDP target ids rotate whenever the browser restarts; a baked-in
   target makes the driver fail every attempt (`rc=1`, stale id).  The supervisor resolves
   the tab itself via `harness/pick_target.py` at start and re-resolves in its loop.
3. Wait ~60s; verify `driver start` in the supervisor log (target = the CURRENT tab id)
   and a fresh ATTEMPT in driver.log.
4. Stale locks are fine — acquire_lock checks pid liveness and replaces dead locks.

## Dynamic target resolution (use everywhere instead of hardcoded ids)
- Own tab:    `TARGET="$(HERMES_BOARD=proving-ground python3 harness/pick_target.py)"`
  (exit 1 = no tab → open one:
   `curl -X PUT "http://127.0.0.1:9223/json/new?https://app.grayswan.ai/arena/challenge/proving-ground"`
   ; exit 2 = ambiguous → do NOT guess, inspect the tabs).
- Sibling tab (to restore as active after own browser ops):
  `SIB="$(HERMES_BOARD=lucky-break-payday python3 harness/pick_target.py)"`
  `curl -s -X PUT "http://127.0.0.1:9223/json/activate/$SIB"`   (returns "Target activated")

## Hard rules (sibling coexistence — RULES 61/70–72)
- NEVER pause: no `loop.paused`, no restart-flags as pause, no lowering max-hours to stop early.
- NEVER touch: lane main, `Lucky Break: Payday`, `artifacts/lane-auto/*`,
  `tools/loop_watchdog.sh`, `tools/lane_auto.sh`, `tools/run1.sh`,
  `harness/loop.py`, `harness/lbp.py`.
- ALL browser ops only with `HERMES_BOARD=proving-ground` and the dynamically resolved
  `$TARGET` (never a hardcoded target id).
- After ANY browser action, restore the sibling tab as active (browser-level CDP
  activate, target id resolved dynamically as above).
- Do NOT launch speculative frames/batches at night — PG personas refuse them; monitor +
  resume + judge strays only.
- Node for browser js: `/c/hermes-tools/node-26.12.1-win32-x64/node.exe`.

## Optional stray-judge step (only if trivially visible)
If a fresh `artifacts/farm-*-send-result.json` shows `class=comply_full` and its chat has no judge yet:
`python3 harness/chat_ops.py judge --target "$TARGET" --chat-id <cid> --scenario-id <scene> --track Chat --opid night-judge-<hhmm>`
(cid via `python3 harness/chat_ops.py find --target "$TARGET"`, or the judge-result naming; scenes in `boards/proving-ground.json`).

## Log line (append to `artifacts/night-pg-watch.log`)
`<HH:MM> | OK|RESUMED | attempts=<N> | last=<first ~60 chars of the last attempt line>`

Final response of each watch run = ONE short line, e.g. `PG watch 00:15 — OK (attempts=170)`
or `PG watch 00:30 — RESUMED (was stuck; supervisor restarted)`.

## OPERATOR STAND-DOWN (2026-11-15 ~22:45) — ACTIVE
- Operator order: stop the PG-solving agent ("пока не решай эту арену; соседние не трогай").
- Done: PG supervisor + driver stopped (kill tree pid 8552); the pg-night-watch cron
  (f5ef855805c7) is PAUSED.
- Untouched and healthy: lane main + its keeper/custodian (the custodian manages lane main
  only and never pokes PG).
- RESUME on operator word: (1) resume the cron (cronjob_manage resume f5ef855805c7);
  (2) start supervisor, background + persist_on_release, HERMES_BOARD=proving-ground,
  NO --target (`python3 harness/supervisor.py --lane pg --port 9223 --db artifacts/harness-pg.db --max-hours 0`);
  (3) verify driver start + a fresh ATTEMPT; the stale lock is replaced automatically.
