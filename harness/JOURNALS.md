# Учёт (journals) — кто источник правды (2026-11-13, RULES 65)

Аудит участника: «журналов правды четыре». Ниже — закреплённая роль каждого.
Правило: **один писатель на журнал**, остальные — только чтение/выгрузка.

| Файл | Роль | Кто пишет | Кто читает |
|---|---|---|---|
| `artifacts/harness.db` (WAL) | **ИСТОЧНИК ПРАВДЫ v2**: `pairs`, `attempts`, `deltas`, `leases`, `events` | только `store.py` (владелец — `driver.py`, один на лейн) | driver, экспорт, аналитика |
| `datasets/lbp/pairs.jsonl` | исторический журнал **v1** (append-only) | только устаревший путь `lbp.py` (v1); после 13.11 новых писателей нет — `lbp_update*.py` выведены в архив | аналитика/реплеи |
| `artifacts/lbp-board.json` | **сид-снапшот** доски (что решено/лучший вход) | вручную/из судейских файлов; driver читает ОДИН раз при seed | `driver.seed()` |
| `artifacts/export/*` (export_pairs.py) | **read-only выгрузка** для отчётов (помечается `derived: true`) | экспортёр (из harness.db) | отчёты/агенты |

## Что выведено из эксплуатации (2026-11-13)
- `harness/lbp_update*.py` (15 скриптов) — дописывали старый журнал v1 → перенесены в `archive/legacy/harness/`; в `harness/` больше не лежат.
- `harness/loop.py` — v1-петля: остаётся как исторический код, но (а) разрешён только при отсутствии v2-супервизора (`artifacts/supervisor.lock` с живым pid → отказ), (б) сценарии/модели берёт из `lbcore.py` (борд-профиль), не из собственной копии.
- Крон-вотчдоги (`pg-loop-watchdog*`) — на паузе (RULES 65); v2 не использует cron.

## Поток исполнения v2 (один вход)
`supervisor.py --lane main` (CDP **9223**, профиль `browser-data`, борд из `boards/lucky-break-payday.json`)
→ `driver.py` (лиз на лейн, UCB по дельтам, попытки `attempts` в harness.db)
→ `lbp.py repeat` (фактический прогон в арене) → `judge_correlation.py` (только свежий судья)
→ запись результата в harness.db → (по желанию) `export_pairs.py` → отчёты.

Профили бордов: `boards/*.json` (`boards.py`), дефолт — `lucky-break-payday` (`DEFAULT_BOARD`).