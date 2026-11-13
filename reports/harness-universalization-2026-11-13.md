# Универсализация харнесса: доска как данные (2026-11-13)

Задача участника: «сделать харнесс более универсальным: рабочий цикл заточен под Lucky Break: Payday;
доска, модели, каталог преобразований и проверка перед отправкой должны приходить из профиля,
а `lbp.py` остаться только браузерным шагом».

## Что сделано

| Зашитое место (было) | Стало (профиль `boards/<board>.json`) |
|---|---|
| `lbcore.MODELS` (4 модели Payday) | `models` (+ `models_by_scenario` для пер-сценарных ростеров) |
| `lbcore.SOLVED` (словарь решённых пар) | `solved_seed` |
| `lbcore.SCENARIO_PREFIX` / `MODEL_SUFFIX` | `scenario_prefixes` / `model_suffixes` |
| префиксы файлов `lbp-` (в драйвере и lbp.py) | `file_prefix` (= `lbp` для Payday, `pg` для Proving Ground) |
| каталог преобразований в `lbcore.DELTAS` | модуль из `deltas_module` (`deltas_payday.py`, новый `deltas_pg.py`) |
| `lbp.py: import lbp_checks` | модуль из `checks_module` (новый `pg_checks.py`) |
| `lbp.py` константы MATCH/BOARD/WIN/TITLES/HINTS/MOCK_SIGNS | профиль (`match`, `board`, `win_string`, `scenario_titles`, `card_hints`, `mock_signs`) |
| `lbp.py` выбор сценария = только клик по карточке | ветка по `scenario_selector`: `card` (Payday) или `behaviorId` (`?behaviorId=` — PG) |
| трек (`Chat`) в bind_scope | `track_default` + `track_by_scenario` (`tamper` → `Image` и т.п.) |
| `supervisor.py` / `driver.py`: `load_board("lucky-break-payday")` | `load_board()` — слушает `HERMES_BOARD` (дефолт прежний) |
| `pick_target.py`: игла `lucky-break-payday` | match из профиля (`--pg` сохранён) |
| один `supervisor.lock` / `run-manifest.json` на воркспейс | пер-борд: `supervisor-<board>.lock`, `run-manifest-<board>.json` (у Payday — прежние имена) |
| `store.py` DDL default `'lucky-break-payday'` | `'default'` (все вставки и так явные; старые БД не затронуты) |
| `manifest.py`: жёсткий `delta_catalog_version=1` | из `generation.DELTA_VERSION` + поле `delta_catalog_module` |
| выбор пар без базы (спин «no base input») | `pick_pair` фильтрует пары без `best_input` |

## Как запускать другую доску

```bash
export HERMES_BOARD=proving-ground          # включается профиль boards/proving-ground.json
python3 harness/supervisor.py --lane pg --port 9223 --target <PG-tabId>   # свой лейн, не трогает Payday
# всё остальное (farm/chat_ops/arena_chats/lbp.py repeat) подхватывает тот же профиль
```

PG-профиль заполнен сценариями (id → title + файловые префиксы):
`proving-defcon33-secvc`, `proving-defcon33-afterparty`, `proving-defcon33-tamper` (Image — цикл текстовый,
образ не умеет: ручной путь), `vulnerable-toolcall`, `incorrect-hotel`.
Базы берутся из `inputs/pg-<prefix>-*.txt` (newest_input).

## Совместимость Payday (живой автопилот)

- Значения по умолчанию идентичны прежним: `MODELS/SOLVED/DELTAS` совпадают побитово (36 дельт),
  имена файлов судьи/транскрипта те же (`lbp-<sid>-<model>-judge.json`), сид пар из `artifacts/lbp-board.json`.
- `python3 harness/run_offline_tests.py` → **tests=64 failures=0 errors=0 skipped=1** (как в baseline).
- `python3 harness/acceptance.py` (offline) → **2/2 PASS**.

## Проверено

- `HERMES_BOARD=proving-ground python3 -c "import lbp"` → match=proving-ground, selector=behaviorId, win='Break Successful!',
  треки (secvc=Chat, tamper=Image), `lbcore` → 13 моделей, 20 дельт (pg-каталог), префикс `pg`.
- `pick_target.py`: дефолт → вкладка Payday; `HERMES_BOARD=proving-ground` → вкладка PG.
- PG dry-run драйвера: см. `artifacts/harness-pg.db` (pairs с базами, attempts).
- Коммит: `6a84238`.

## Дальше

1. Запустить PG-супервизор (свой лейн `pg`) → цикл гоняет дельты по базам PG.
2. Дополнить базы (inputs/pg-*) по мере решения; tamper — только вручную (Image).
3. `pg_checks.SCENARIO_TOOL` пополнять маркерами тул-сценариев (сейчас `subtract`, `book_room`).
