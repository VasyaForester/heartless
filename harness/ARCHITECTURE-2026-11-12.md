# Harness architecture v2 — 2026-11-12

## Why v1 stopped

v1 was a set of finite bash "waves" (`tools/chainNN.sh`): 4-6 probes, exit, then wait
for the agent to write the next one. The watchdog was a cron that checked `ps`/`pkill`;
on Windows `pkill` does not kill Python processes, so each restart added a duplicate.
The judge was a filename (`artifacts/lbp-*-judge.json`), so a failed attempt could read
a stale verdict and the board never moved. The "autoping" only printed to a log; it did
not wake the agent. There was no lease, no single writer, no real supervisor.

## v2 layers

1. **Supervisor** — `harness/supervisor.py`. One long-lived process. Starts the lane
   Chrome if CDP is down; **never kills a browser**. Restarts the driver on exit.
   No cron, no `pkill`, no `Stop-Process`, no manual confirmation.
2. **Driver** — `harness/driver.py`. One worker per lane. SQLite state, lease,
   heartbeat, UCB over deltas, backoff. `restart.requested` is the cooperative stop.
3. **State** — `artifacts/harness.db` (WAL): `pairs`, `attempts`, `deltas`, `leases`,
   `events`. One writer. Judge is read only if its mtime is newer than `t0`.
4. **Lease** — `(lane, pid, target, heartbeat)`. A second driver refuses to start if the
   lease is fresh and the pid is alive. This replaces `ps`/`pkill` and kills duplicates
   by construction.
5. **Graph RAG** — `harness/kb_graph.py`. SQLite FTS5 over the KB/datasets/raw READMEs,
   typed nodes (`source`, `benchmark`, `scenario`, `technique`, `paper`, `model`, `doc`)
   and edges (`mentions`, `cites`, `related`, `maps_to`). Retrieval = FTS seed -> 1-hop
   expansion -> cited chunks. No LLM, no embeddings, no dump in context.

## Operating rules

- No `wave`, `rotation`, `session` as process units. The unit is an attempt/work item.
- No manual confirmation in the loop. The operator starts the supervisor once.
- No killing Chrome. If the CDP port is down, the supervisor starts the lane browser.
- Stop only on a system blocker (auth, energy below floor, explicit operator stop).
- Old `chainNN.sh`, `loop_watchdog.sh`, `pg-autoping`, `combat-queue` are archived
  under `archive/legacy/`; do not use them.

## Commands

```bash
# one long-lived supervisor (auto lane, CDP 9224, browser-data-auto)
python3 harness/supervisor.py --lane auto --max-hours 0

# one-shot smoke test (no infinite loop)
python3 harness/supervisor.py --lane auto --once --dry-run
python3 harness/supervisor.py --lane auto --once

# graph RAG
python3 harness/kb_graph.py build
python3 harness/kb_graph.py query "gift card discount structure"
python3 harness/kb_graph.py related bench:injecagent
python3 harness/kb_graph.py stats

# cooperative stop/restart of the driver
touch artifacts/lane-auto/restart.requested   # driver exits; supervisor restarts
```