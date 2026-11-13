# Harness — структура и описание (2026-11-12)

Профиль: `C:\Users\Василий\AppData\Local\hermes\profiles\gray-swan-hackathon-v2`
Корень: `workspace`
Назначение: непрерывное решение задач Lucky Break: Payday (LBP) и Proving Ground (PG), ведение попыток, судейских вердиктов и базы знаний.

Статусы в дереве:

- **LIVE** — живая инфраструктура автопилота; защищена правилом 61 `RULES.md`, не удалять и не переписывать без теста.
- **LIVE-AUX** — используется живым контуром, но не входит в защищённый список.
- **V2** — новый слой (SQLite/lease/supervisor/Graph RAG/board-профили); работает параллельно, live-петлю пока не заменяет.
- **LEGACY** — старые волны/журналы/утилиты; сохранены, но continuous-петлёй не используются.
- **DATA / KNOWLEDGE** — состояние, корпуса, выгрузки.

---

## 1. Дерево верхнего уровня

```
workspace/
├── RULES.md                         # 61 правило; правило 61 = защищённые live-файлы
├── CLAUDE.md                        # operating mode: не останавливаться, без волн/ручных гейтов
├── boards/                          # V2: профили досок (данные, без логики)
│   ├── README.md
│   ├── lucky-break-payday.json
│   └── proving-ground.json
├── harness/                         # рантайм, CLI, транспорт, проверки, граф
├── tools/                           # live-автопилот + утилиты + legacy-волны
├── datasets/                        # журналы, критерии, корпуса, каталоги источников
├── artifacts/                       # состояние, БД, логи, judge/transcript-квитанции
├── inputs/                          # 2 541 файл: scope-файлы и payload-пробы
├── deliverables/                    # отчёты, handoff'ы, консультации, презентации
├── prompt_injection_ctf/            # корпус знаний: knowledge_base, benchmarks, attacks, raw/sources
└── archive/legacy/                  # 93 файла старого контура (волны, watchdog, lbp_update)
```

---

## 2. `harness/` — рантайм

### 2.1 Транспорт и живой CLI

| Файл | Статус | Что делает |
|---|---|---|
| `hackathon.py` | LIVE-AUX | Транспорт: CDP, вкладки, `fill`, один `send`, `arena judge`, скриншоты. Не решает, какая доска/сценарий — это вынесено в профили и вызывающий CLI. 36 KB. |
| `lbp.py` | **LIVE** | Живой CLI LBP: `state`, `switch`, `check`, `submit`, `verdict`, `repeat`, `export`, `cards`, `chats`, `newchat`, `eval`, `reload`. Держит константы доски, `lbp_tab_id()` (ровно одна LBP-вкладка), `looks_like_refusal()`, `autosubmit_allowed()`, duplicate-gate по `repeats.jsonl`. 38 KB. Защищён правилом 61. |
| `loop.py` | **LIVE** | Непрерывный драйвер v1: выбирает нерешённую пару, мутирует payload дельтой, вызывает `lbp.py repeat --submit`, читает judge, обновляет board/bandit, пишет heartbeat. Экспортирует `DELTAS`, `SCENARIOS`, `MODELS`, `SOLVED`, `run_attempt`, `read_judge`, `newest_input`. 25 KB. Защищён. |
| `farm.py` | LIVE-AUX | Обёртка Proving Ground: `bind_scope`, выбор сценария через `?behaviorId=`, чекпойнты `artifacts/farm-<board>-<scenario>.json`. 16 KB. |
| `chat_ops.py` | LIVE-AUX | Работа с модалкой чатов: `find`, `open`, `meta`, `read`, `followup`, `judge`. Явный `--target` обязателен; `BASE_URL` — PG. 12 KB. |
| `arena_heal.py` | LIVE-AUX | Judge/heal-операции арены (повторный разбор, восстановление состояния). 9 KB. |
| `arena_chats.py` | LIVE-AUX | Список чатов и привязка строк к `chatId`. 6 KB. |
| `pick_target.py` | LIVE-AUX | Выбирает CDP-вкладку по порту из `HACKATHON_CDP_URL`; не наследует `CHAT_TARGET` между лейнами. 1 KB. |
| `classify_response.py` | LIVE-AUX | Классификация ответа: отказ / печатный псевдо-вызов / реальная инвокация. 5 KB. |
| `campaign.py` | LIVE-AUX | Кампании/планы, гипотеза прогона, note. 5 KB. |

### 2.2 V2 — новый слой

| Файл | Статус | Что делает |
|---|---|---|
| `driver.py` | V2 | Один worker на лейн. SQLite WAL `artifacts/harness.db`: `pairs/attempts/deltas/leases/events`. Lease с heartbeat, UCB по `pcts`, judge только если файл новее старта попытки, `rc != 0` не обновляет board, backoff без выхода, кооперативный стоп `<state_dir>/restart.requested`. Импортирует константы/`run_attempt` из `loop.py`. 15 KB. |
| `supervisor.py` | V2 | Долгоживущий процесс: поднимает Chrome только если CDP down, **никогда не убивает браузер**, перезапускает driver после выхода, окна за краем экрана (`--window-position=-32000,-32000`), URL из board-профиля. 5 KB. |
| `kb_graph.py` | V2 | Graph RAG: SQLite FTS5 + типизированный граф (`source/benchmark/scenario/technique/paper/model/doc`), команды `build/query/related/stats`, без LLM/эмбеддингов. 15 KB. Сейчас: 557 docs, 5 950 chunks, 2 432 nodes, 24 370 edges. |
| `boards.py` | V2 | Загрузчик/валидатор профилей досок; `load_board()`, `active_board()`, `list_boards()`. |
| `refusal_guard.py` | V2 | Обёртка проверки: если транскрипт — отказ, `ready=False` даже при цитате целевого вызова. Живой `lbp.py check` пока не использует; acceptance проверяет обёртку. |
| `acceptance.py` | V2 | Четыре проверки из рекомендации 2026-11-12: профиль доски == константы `lbp.py`; отказ с цитатой не `ready`; live `state` guard; live `switch`; опционально live `submit`. Offline: 2/2 PASS. |
| `export_pairs.py` | V2 | Экспорт SQLite → `datasets/lbp/pairs-v2.jsonl` (20 пар), не пишет обратно. |

### 2.3 Проверки и судейство

| Файл | Статус | Что делает |
|---|---|---|
| `lbp_checks.py` | LIVE-AUX | Пайплайн проверки tool-call по контракту сценария; вызывает `lbp_contracts.json`. |
| `lbp_contracts.json` | LIVE-AUX | Контракты сценариев: точные типы/аргументы инструментов, критерии. |
| `lbp_checks_test.py` | LIVE-AUX | Мини-тест пайплайна проверок. |
| `lbp_eval_row.py` | LIVE-AUX | Разбор строки `SEE EVALUATION` в структуру. |
| `verdict_sweep.py` | LIVE-AUX | Сбор/свод вердиктов. |
| `verdict_verify.py` | LIVE-AUX | Проверка вердикта/квитанции. |
| `scenario_filters.py` | LIVE-AUX | Фильтры сценариев/моделей. |
| `pending.py` | LIVE-AUX | Учёт pending-сабмитов. |
| `tried.py` | LIVE-AUX | Что уже пробовали (индекс `tried-index`). |
| `unicode_hide.py` | LIVE-AUX | Unicode-обфускация полезной нагрузки. |

### 2.4 Браузерные помощники и JS-пробы

| Файл | Что делает |
|---|---|
| `new-chat.mjs`, `click-chat-row.mjs`, `close_browser.mjs`, `copy-cookies.mjs`, `debug-dom.mjs`, `render-image.mjs`, `eval-page.mjs` | CDP/Node-операции: новая вкладка, клик по строке чата, закрытие браузера, перенос куков между профилями, DOM-дамп, рендер, eval. |
| `probe-chat.js`, `read-text.js`, `chat-links.js` | Пробы: модель/баннер/judge, текст ответа, ссылки чатов. |
| `lbp_js/` | JS-пробы LBP: `state.js`, `chatread.js`, `cards.js`, `verdict.js`. |
| `ipi_js/` | JS-пробы IPI-корпуса. |
| `tests/` | Фикстуры/тест `lbp_checks_test.py`; вложенная `.upload-fixture-*`. |

### 2.5 Документация harness

| Файл | Что содержит |
|---|---|
| `ENGINE.md` (13.9 KB) | Точные команды запуска, переменные, режимы. |
| `HARNESS-IMPROVEMENTS.md` (21.7 KB) | Рецепты и грабли, накопленные по ходу. |
| `HARNESS-TOOLS.md` (9.7 KB) | Каталог инструментов. |
| `LBP.md` (5.4 KB) | Устройство доски LBP. |
| `DECISION-TREE.md` (7.8 KB) | Дерево решений по классам отказов. |
| `TECHNIQUES.md` (7.3 KB) | Техники обхода/классы payload. |
| `ARCHITECTURE-2026-11-12.md` (2.8 KB) | Краткое описание v2. |

### 2.6 LEGACY в `harness/`

`lbp.py.bak` (старый CLI), `lbp_blitz.py`, `lbp_plan.py`, `lbp_roster.py`, `lbp_accum.py`, `lbp_events.py`, `lbp_report.py`, `lbp_update_20261110.py` + `lbp_update2..15_*.py` (13 скриптов журнала), `wave_scan.py`, `switch-wave.mjs`. Это «волны» и пошаговые апдейтеры; continuous-петля их не использует. Сохранены по требованию участника, не удалять.

---

## 3. `boards/` — профили досок (V2)

| Файл | Что содержит |
|---|---|
| `lucky-break-payday.json` | `match=lucky-break-payday`, URL, `scenario_selector=card`, `model_confirm=Attacking:`, `win_string=SCENARIO SOLVED`, `cost={message:1,judge:1}`, `scenario_titles`, `card_hints`, `mock_signs` (5 сценариев). |
| `proving-ground.json` | `match=proving-ground`, URL, `scenario_selector=behaviorId`, `win_string=Break Successful!`, `cost`. Отдельный профиль, чтобы чекпойнты PG и Payday не затирали друг друга. |
| `README.md` | Схема полей и порядок добавления новой доски. |

Профиль — только данные; `hackathon.py` остаётся транспортом. `acceptance.py` проверяет, что Payday-профиль совпадает с константами живого `lbp.py`.

---

## 4. `tools/` — live-автопилот, утилиты, legacy

### 4.1 LIVE (правило 61)

| Файл | Что делает |
|---|---|
| `loop_watchdog.sh` | Сторож auto-лейна: heartbeat `artifacts/lane-auto/loop-heartbeat.json`; если старше порога — перезапускает драйвер; `FORCE_RESTART`; self-heal Chrome 9224; не убивает основной браузер. |
| `lane_auto.sh` | Запуск auto-лейна: Chrome 9224, профиль `browser-data-auto`, окно за краем экрана, `pick_target`, старт `loop.py`. |
| `run1.sh` | Одиночный прогон/подъём лейна. |

`~/AppData/Local/hermes/scripts/loop_watchdog.sh` — шим на `workspace/tools/loop_watchdog.sh`; его вызывает cron. Тоже защищён правилом 61.

### 4.2 Данные/утилиты

| Файл | Что делает |
|---|---|
| `fetch_web_20261112.py` | Догрузка web/abs-страниц (без PDF), сохраняет `raw/sources/web/<key>.html|.md`, пишет `manifest.jsonl`. Сейчас включает 8 новых источников 2026-11-12. |
| `arena_state.py` | Снимок состояния арены. |
| `build_tried_index.py` | Индекс «что уже пробовали». |
| `pg_pairs.py`, `pg_build_s2.py`, `pg_build_s4.py`, `pg_build_s4b.py`, `pg_eval_capture.py`, `pg_journal_map.py`, `pg_snap.py` | Proving Ground: пары, сборка сценариев, захват оценки, журнал, снимки. |
| `fill_pptx.py`, `pptx_dump.py` | PPTX-заполнение/дамп. |
| `html2txt.py`, `inspect_texts.py`, `show_msgs.py`, `read_criteria.py`, `check_export.py`, `make_harness_diagram.py`, `ipi_collect_criteria.py` | Мелкие утилиты: текст, сообщения, критерии, экспорт, диаграмма. |
| `pg_autoping.sh` | PG-пинг (вспомогательный). |

### 4.3 LEGACY

`chain38b..chain105.sh` — конечные «волны» по 4–6 проб; `ladder1..3.sh` — лестницы. Восстановлены из git после инцидента 13:25, но continuous-петлёй не используются. Удалять нельзя только файлы из правила 61; эти — исторические, но лучше не трогать без нужды.

---

## 5. `datasets/` — журналы, критерии, корпуса

| Файл | Что содержит |
|---|---|
| `agent-security-benchmarks-2026-11-12.md` | Каталог 61 источника + дополнение из 8 работ 2026 по защитным механизмам (AIRGuard, PolicyGuide, AgentAbstain, Anthropic self-assessment, PolicyGuard, MDPI IPI defenses, EMNLP multi-agent debate, WorkBench Revisited). |
| `lbp/pairs.jsonl` | 20 пар `scenario|model`: solved, best_input, attempts, verdict, notes. Живой журнал v1. |
| `lbp/pairs-v2.jsonl` | V2-экспорт из SQLite (20 пар, last_attempt). Производный, не источник истины. |
| `lbp/repeats.jsonl` | Каждая проба: input hash, output, judge; duplicate-gate. 693 KB. |
| `lbp/loop-results.jsonl` | Результаты v1-петли. 280 KB. |
| `lbp/criteria.json` | Критерии судьи по сценариям. |
| `lbp/decision-tree.json` | Дерево решений/классов. |
| `lbp/mock-map.json` | Мок-подписи сценариев. |
| `lbp/model_matrix.md` | Матрица сценарий × модель. |
| `lbp/corpus-classes-v3/v4/v5-refund-techniques.md` | Корпуса классов (включая 49 KB refund-техник). |
| `lbp/corpus-stored-value-2026-11-12.md` | Gift-card/stored-value fraud: таксономия, риск-сигналы, критерии. |
| `lbp/benchmark-derived-classes-2026-11-12.md` | Маппинг бенчмарков на сценарии LBP/PG. |
| `lbp/controls.md`, `tensor-trust-*.md`, `tried-index.*`, `ui_fixtures.jsonl`, `verdict_strings.jsonl`, `roster_snapshot.json` | Контроли, TensorTrust, tried-индекс, UI-фикстуры, строки вердиктов, ростер. |
| `lbp/README-v2.md` | Единица работы v2 (attempt/work item вместо wave). |
| `lbp/combat-queue.md` | LEGACY: очередь волн. |

---

## 6. `artifacts/` — состояние и доказательства

| Путь | Что содержит |
|---|---|
| `harness.db` | V2 SQLite (WAL): `pairs`, `attempts`, `deltas`, `leases`, `events`; 20 пар, 12 решено на момент снимка. |
| `kb_graph.db` | Graph RAG: FTS5 + типизированный граф. |
| `lbp-board.json` | V1-доска: 12/20, best_input, deltas, score. |
| `lane-auto/` | LIVE: `loop-heartbeat.json`, `loop.pid`, `loop.out`, `FORCE_RESTART`, `loop.paused`. |
| `lane-main/` | Главный лейн; Chrome 9223 закрыт навсегда, лейн на паузе. |
| `driver.log`, `supervisor.log` | Логи v2. |
| `lbp-<scenario>-<model>-judge.json` | Квитанции судьи по парам. |
| `lbp-...-submit-transcript.json` | Снимок транскрипта перед судом + hash. |
| `_chatops_chats_*.json` | Сырые probe-выгрузки чатов (много; группа). |
| `link-inventory-2026-11-12.json` | known/missing/61 + addendum 8. |
| `AUTOSUBMIT_DECISION-2026-11-12.txt` | Решение участника об автосабмитах (риск принят). |
| `loop_watchdog.stale-20261111.sh.bak` | Бэкап старого шима. |

---

## 7. `inputs/` — 2 541 файл

`scope-lbp-*.json` — привязка модели/сценария; `lbp-*.txt` — payload-пробы (включая loop-дельты); `pg-*` — Proving Ground; `ipi-*` — IPI-корпус. Имена несут сценарий, модель, дельту и timestamp.

---

## 8. `deliverables/` — отчёты и handoff'ы

Ключевые: `SOLVER-RULES.md` (политика решения), `ipi-knowledge-structure.md` (структура корпуса), `handoff-2026-11-11-lbp-state.md` (состояние LBP), `harness-improvement-plan-2026-11-12.md`, `HARNESS-IMPROVEMENT-REPORT-2026-11-07.md`, `PG-W1-LIVE-2026-11-10.md`, консультации `chatgpt-*`/`lbp-consult-*`, `presentation-content.md`, `harness-architecture.png`, pptx/zip-архивы. Это история решений и внешние ответы, не рантайм.

---

## 9. `prompt_injection_ctf/` — корпус знаний

- `knowledge_base/` — структурированные заметки (00_index и домены).
- `benchmarks/` — описания бенчмарков.
- `attacks/` — техники атак.
- `challenges/`, `evaluation/`, `novel_discoveries/`, `processed/`, `rag/`, `reports/`, `research_v2/` — задачи, оценка, находки, RAG-артефакты.
- `raw/` — исходные датасеты (agentdojo, injecagent, bipia, gandalf, tensortrust, prompt-injection-5k и др.).
- `raw/sources/` — выгрузки: `artifacts/` (`fetch_artifacts.py`, `manifest.jsonl`, `links.jsonl`, github/huggingface), `arxiv/` (`abs`, `html`, `papers`), `web/` (14 старых + 9 новых; MDPI — metadata-only), `attachments/` (`list-agent-security-2026-11-12.txt` 61 + addendum 8), `elder-plinius/`, `hf-datasets/`, `unicode-ucd-18.0.0/`.

---

## 10. `archive/legacy/` — 93 файла

Копии старого контура: `tools/chain*.sh`, `loop_watchdog.sh`, `lane_auto.sh`, `pg_autoping.sh`, `harness/lbp_update*.py`, `lbp_blitz/plan/roster/accum/events/report.py`, `wave_scan.py`, `switch-wave.mjs`, `datasets/lbp/combat-queue.md`. Это НЕ live; live-файлы восстановлены в `tools/`/`harness/` из git (коммит `79fccd7`, правило 61).

---

## 11. Потоки выполнения

### LIVE v1
```
cron / tools/loop_watchdog.sh
  → tools/lane_auto.sh (Chrome 9224, offscreen)
  → harness/loop.py (heartbeat)
      → harness/lbp.py repeat --submit
          → hackathon.py (CDP: fill/send)
          → lbp.py check → judge
      → read_judge → loops/deltas → artifacts/lbp-board.json
```

### V2 (параллельный слой)
```
harness/supervisor.py
  → harness/driver.py (SQLite WAL, lease, UCB)
      → loop.run_attempt (live)
      → read_judge(since=t0) → attempts/deltas/events
      → restart.requested — кооперативный стоп
```

### Граф знаний
```
prompt_injection_ctf/knowledge_base + benchmarks + attacks
+ datasets/**/*.md + deliverables/ipi-*
  → harness/kb_graph.py build → artifacts/kb_graph.db (FTS5 + typed graph)
  → query/related/stats
```

### Одна попытка (стадии)
```
state → switch (panelTitle + Attacking:) → scope → один send → wait
→ check (tool-call по контракту, отказ ≠ ready) → judge → журнал
```

---

## 12. Результаты проверок на 2026-11-12

- `harness/acceptance.py` (offline): **2/2 PASS**.
  - `boards`: Payday-профиль == константы `lbp.py`.
  - `refusal`: `raw_ready=True`, `guarded_ready=False`, `refused=True` — цитата вызова в отказе больше не проходит.
- `py_compile`: `boards.py`, `refusal_guard.py`, `acceptance.py`, `export_pairs.py`, `supervisor.py`, `driver.py` — OK.
- `export_pairs.py`: 20 пар → `datasets/lbp/pairs-v2.jsonl`.
- `kb_graph.py build`: 557 docs, 5 950 chunks, 2 432 nodes, 24 370 edges.
- Источники 2026-11-12: 9/10 HTTP 200; MDPI 403 (Akamai), аннотация получена через Crossref (`10.3390/computers15090570`), dataset Zenodo 200. `openreview` (старый, не из addendum) отдаёт browser-check.

---

## 13. Что смотреть другим моделям (честные пробелы)

1. **Live `lbp.py` не использует `refusal_guard`**: `check`/`submit` по-прежнему могут пометить цитату в отказе как `ready`; guard проверен только в `acceptance.py` и пока не вшит в живой CLI. Это главный незакрытый пункт рекомендации.
2. **Live `state` CLI не вызывает `lbp_tab_id()`**: библиотечный guard есть (ровно одна вкладка / явный `--target`), но `lbp.py state` его не вызывает; acceptance тестирует библиотеку, не CLI.
3. **`pairs.jsonl` vs SQLite**: рекомендация называет `pairs.jsonl` единственным журналом; фактически живой журнал — `pairs.jsonl` (v1), а v2-истина — `harness.db`; `pairs-v2.jsonl` — производный экспорт. Нужно решение, какой слой главный.
4. **Один вход не завершён**: `hackathon.py` (транспорт), `lbp.py`, `farm.py`, `chat_ops.py` всё ещё держат свои константы/URL; board-профили подключены к `supervisor.py`, но не к живому `lbp.py`/`farm.py`/`chat_ops.py`.
5. **V2 не live**: `driver.py`/`supervisor.py` не запущены; автопилот — `loop.py` + `tools/loop_watchdog.sh`. `driver.py` импортирует `loop.py` (live), т.е. v2 зависит от защищённого файла.
6. **Legacy-шум**: `lbp_update*.py` (13), `lbp_blitz/plan/roster/accum/events/report`, `wave_scan.py`, `switch-wave.mjs`, `tools/chain*.sh`, `ladder*.sh`, `combat-queue.md`, `lbp.py.bak` — не используются continuous-петлёй, но лежат в рабочих каталогах.
7. **Нет тестов driver/supervisor**: acceptance покрывает профили и refusal; SQLite/lease/UCB/supervisor не имеют unit-тестов.
8. **Автосабмиты**: правило 59 — автоматика включена решением участника, риск дисквалификации принят; рубильник `artifacts/BLOCK_AUTOSUBMIT.txt` / `LBP_BLOCK_AUTOSUBMIT=1`.
9. **MDPI 403**: полный текст не получен; в корпусе только Crossref-аннотация. Для репликации нужен другой маршрут (VPN/PDF из институционального доступа).
10. **Дубликаты `_chatops_chats_*.json`** (сотни) не чистились; это диагностические выгрузки, не состояние.

---

## 14. Быстрые команды

```bash
# профиль доски
python3 harness/boards.py

# офлайн-проверки
python3 harness/acceptance.py

# live-проверки (не на живой петле)
python3 harness/acceptance.py --live

# v2 dry-run
HACKATHON_CDP_URL=http://127.0.0.1:9224 python3 harness/driver.py --lane auto --dry-run --once

# экспорт пар
python3 harness/export_pairs.py

# граф
python3 harness/kb_graph.py build
python3 harness/kb_graph.py query "gift card discount structure" --limit 6

# живые проверки автопилота (не трогать без нужды)
bash tools/loop_watchdog.sh
```