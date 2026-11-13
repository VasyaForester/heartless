# NIGHT WATCH — PG lane (sibling) — night of 2026-11-13/14

Standing order from the operator: keep Proving Ground solving CONTINUOUSLY through the night;
NEVER pause; verify every 15 minutes; if something is stuck — resume it.

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
   The 5 solved `proving-defcon33-secvc` pairs are INTENTIONALLY marked — never reset.

## Resume procedure (only if STUCK: supervisor dead, or no attempt line for >20 min)
1. Kill our leftovers only:
   `MSYS_NO_PATHCONV=1 taskkill /F /T /PID $S` (ignore errors)
   `ps -W | grep python3.12` — inspect, kill ONLY processes running `driver.py --lane pg`
   (do NOT touch lane=main / keeper / lucky-break processes).
2. Relaunch (MUST outlive the cron session — background=true, persist_on_release=true):
   `HERMES_BOARD=proving-ground python3 harness/supervisor.py --lane pg --port 9223 --target DBBAABBDF316BFB73616588BF041EA12 --db artifacts/harness-pg.db --max-hours 0`
3. Wait ~60s; verify `driver start` in the supervisor log and a fresh ATTEMPT in driver.log.
4. Stale locks are fine — acquire_lock checks pid liveness and replaces dead locks.

## Hard rules (sibling coexistence — RULES 61/70–72)
- NEVER pause: no `loop.paused`, no restart-flags as pause, no lowering max-hours to stop early.
- NEVER touch: lane main, `Lucky Break: Payday`, tab `D769D07296DFEAD5E66D6AF990ECF0F9`,
  `artifacts/lane-auto/*`, `tools/loop_watchdog.sh`, `tools/lane_auto.sh`, `tools/run1.sh`,
  `harness/loop.py`, `harness/lbp.py`.
- ALL browser ops only with `HERMES_BOARD=proving-ground` and `--target DBBAABBDF316BFB73616588BF041EA12`.
- After ANY browser action, restore the sibling tab as active (browser-level CDP `Target.activateTarget`,
  targetId `D769D07296DFEAD5E66D6AF990ECF0F9`, via `http://127.0.0.1:9223/json/version`).
- Do NOT launch speculative frames/batches at night — PG personas refuse them; monitor + resume + judge strays only.
- Node for browser js: `/c/hermes-tools/node-26.12.1-win32-x64/node.exe`.

## Optional stray-judge step (only if trivially visible)
If a fresh `artifacts/farm-*-send-result.json` shows `class=comply_full` and its chat has no judge yet:
`python3 harness/chat_ops.py judge --target DBBAABBDF316BFB73616588BF041EA12 --chat-id <cid> --scenario-id <scene> --track Chat --opid night-judge-<hhmm>`
(cid via `python3 harness/chat_ops.py find --target DBBA…`, or the judge-result naming; scenes in `boards/proving-ground.json`).

## Log line (append to `artifacts/night-pg-watch.log`)
`<HH:MM> | OK|RESUMED | attempts=<N> | last=<first ~60 chars of the last attempt line>`

Final response of each watch run = ONE short line, e.g. `PG watch 00:15 — OK (attempts=170)`
or `PG watch 00:30 — RESUMED (was stuck; supervisor restarted)`.
