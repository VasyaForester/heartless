# LBP state — v2 (2026-11-12)

- `artifacts/harness.db` — SQLite (WAL): `pairs`, `attempts`, `deltas`, `leases`, `events`.
  Единственный источник истины. `pairs.solved`, `best_score`, `best_input`; `attempts` — лог;
  `deltas` — бандит; `leases` — один worker на лейн; `events` — аудит.
- `harness/driver.py` — один worker. Lease, heartbeat, UCB, backoff, `restart.requested`.
- `harness/supervisor.py` — долгоживущий процесс; поднимает Chrome лейна, если CDP down;
  никогда не убивает браузер; перезапускает driver.
- `harness/kb_graph.py` — Graph RAG: `build`, `query`, `related`, `stats`.
- `artifacts/kb_graph.db` — индекс KB + datasets + raw READMEs; FTS5 + типизированный граф.
- Архивировано в `archive/legacy/`: `tools/chainNN.sh` (волны), `tools/loop_watchdog.sh`,
  `tools/pg_autoping.sh`, `datasets/lbp/combat-queue.md`, `harness/lbp_update*.py`,
  `harness/lbp_blitz.py`, `lbp_plan.py`, `lbp_roster.py`, `lbp_accum.py`, `lbp_events.py`,
  `lbp_report.py`, `wave_scan.py`, `switch-wave.mjs`.

Не использовать `wave`/`rotation`/`session` как единицы процесса. Единица — attempt/work item.
Ручных подтверждений в петле нет. Chrome не убивается: supervisor только стартует его при
недоступном CDP.