# Учёт (journals) — кто источник правды (обновлено 2026-11-15)

История: аудит участника (13.11, RULES 65) закрепил роли файлов, но оставил трёх
живых читателей, которые считали матрицу по архиву `datasets/lbp/pairs.jsonl` — а
один из них ещё и ПИСАЛ в него. Обзор Grok (15.11, ось «один журнал»: 4/10) назвал
это точно: архив, который никто не ведёт, выдавался за настоящее.

**Правило теперь одно: матрицу читает только `harness/journal.py`.** Живые
компоненты берут её оттуда; `pairs.jsonl` — архив, его никто не читает как данные и
никто в него не пишет (`config_check.check_single_journal` краснеет, если кто-то
снова начнёт).

| Файл | Роль | Кто пишет | Кто читает |
|---|---|---|---|
| `artifacts/harness.db` (WAL) | **ИСТОЧНИК ПРАВДЫ**: `pairs`, `attempts`, `deltas`, `leases`, `events` | только `store.py` (владелец — `driver.py`, один на лейн) | все — через `harness/journal.py` |
| `harness/journal.py` | **единственный читатель матрицы**: `live_matrix()`, `summary()`, `render_markdown()` | — | `lbp_plan.py`, `lbp_report.py`, `lbp.py cmd_export`, отчёты |
| `datasets/lbp/pairs.jsonl` | **архив v1** (append-only, история цитат отказов) | никто с 15.11 | никто в живом коде (только чтение руками ради истории) |
| `datasets/lbp/pairs-v2.jsonl`, `datasets/lbp/model_matrix.md` | **производные выгрузки** (помечают источник) | `export_pairs.py`, `lbp_report.py` | отчёты/агенты |
| `artifacts/lbp-board.json` | **сид-снапшот** доски (что решено/лучший вход) | вручную/из судейских файлов; driver читает ОДИН раз при seed | `driver.seed()` |

## Что выведено из эксплуатации (2026-11-13)
- `harness/lbp_update*.py` (15 скриптов) — дописывали старый журнал v1 → перенесены в `archive/legacy/harness/`; в `harness/` больше не лежат.
- `harness/loop.py` — v1-петля: **заглушка, выходит с кодом 3**. Формулировки «разрешён,
  если супервизора нет» больше нет (удалена 15.11): она описывала поведение, которого у
  файла не существует. Живой контур — только `supervisor.py → driver.py`.
- Крон-вотчдоги (`pg-loop-watchdog*`) — на паузе (RULES 65).

## Поток исполнения v2 (один вход)
`supervisor.py --lane main` (CDP-порт из окружения или аргумента, профиль `browser-data`,
борд из `boards/<name>.json` через `$HERMES_BOARD`)
→ `driver.py` (лиз на лейн, отбор дельт, попытки `attempts` в harness.db)
→ `lbp.py repeat` (фактический прогон в арене) → `judge_correlation.py` (только свежий судья)
→ запись результата в harness.db → `harness/journal.py` (матрица) → отчёты.

Профили бордов: `boards/*.json` (`boards.py`, схема `boards/schema.json`); доска
задаётся `$HERMES_BOARD` или явным аргументом, `DEFAULT_BOARD` (`lucky-break-payday`)
остаётся только страховкой от пустого окружения.