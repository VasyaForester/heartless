# LBP-слой харнесса (Lucky Break: Payday и общая арена)

Наш рабочий слой поверх упакованного `ENGINE.md` (адаптер организатора).
Всё выполняется из `workspace` импортированного профиля.

## 1. Компаньон доски — `harness/lbp.py`

| Команда | Что делает |
|---|---|
| `state` | URL/вкладка/модель/панель/энергия + список LBP-вкладок |
| `cards` | скан карточек сценариев (`[data-behavior-id]`) |
| `switch --scenario ID [--model NAME]` | клик по сценарию + модели; подтверждение `Attacking: <имя>` |
| `check --scenario ID` | локальные валидаторы V1–V4 (contracts в `lbp_contracts.json`, код в `lbp_checks.py`) |
| `submit --scenario ID [--force]` | сабмит через `farm.bind_scope` + `arena judge`; снапшот транскрипта + sha256 |
| `verdict` | читает панель вердикта на странице |
| `reload` | ритуал для мёртвого вебсокета (потерянные отправки) |
| `chats` | SUBMISSIONS→CHATS, все chatId |
| `eval [--scenario X]` | полный judge receipt (Swan/Phoenix/SCORES) → `artifacts/lbp-eval-*.txt` |
| `repeat --scenario X --model Y --input F --n K [--submit]` | фикс-стратегия × K (pass^k), ledger `datasets/lbp/repeats.jsonl` |
| `export` | сводная выгрузка доски → `deliverables/lbp-final-*.md` |

JS-хелперы: `harness/lbp_js/*.js`; вызов через `chat_ops.evaljs('harness/lbp_js/X.js', match='lucky-break-payday')`.

## 2. Ротация — `harness/lbp_roster.py` + `harness/lbp_blitz.py`

- `lbp_roster.py` — снапшот ростеров всех сценариев; печатает ротацию (`N changed`). **Первый шаг после паузы.**
- `lbp_blitz.py --model "<новая модель>"` — залп 4 рецептов (giftcard / scam / bank / negq-лестница «обычный заказ → фикс знака») с авто-сабмитом по пройденному check. Dry-run: `--dry`.

## 3. Процедуры (грабли, проверенные на практике)

1. **Потерянная отправка** (UI показал «sent», ответа нет >60 c): reload → переслать (НЕ дубликат). Проверка «серверу дошло?» — свежий mount панели (switch away/back) или `chats`.
2. **Сабмит только после `check`** (пустой сабмит = −10 энергии): `check ok` → `submit`.
3. **Receipt сразу после сабмита** (`eval` берёт НОВЕЙШУЮ строку сабмитов).
4. **Одна доска — одна вкладка**: лишняя вкладка делает `--match` неоднозначным (уводить на `/arena`).
5. **Правила участника** (см. `CLAUDE.md`): решённые пары не трогать; пауза активных проб до ротации; платформенные Rules не читать.

## 4. Данные наблюдений — `datasets/lbp/`

- `pairs.jsonl` — матрица 5×4 (chatId, tool_args, outcome, failure_category, attempts, notes);
- `model_matrix.md` — отчёт v2 (`lbp_report.py`: слой×причина, progress_rank, Wilson CI);
- `controls.md` — контроли/инвариантность причин; `fixtures/check_fixtures.json` + `lbp_checks_test.py` (14/14);
- `events/attempts.jsonl` — типизированные события; `repeats.jsonl` — pass^k-повторы;
- `roster_snapshot.json` — ротация; `corpus-classes-2026-11-10.md` — карта 16 классов;
- `ui_fixtures.jsonl`, `verdict_strings.jsonl` — парсер-фикстуры UI.

## 5. Артефакты и корпуса — `prompt_injection_ctf/raw/sources/artifacts/`

- `fetch_artifacts.py` — extract/fetch (GitHub+HuggingFace, кэпы, квитанции в `manifest.jsonl`);
- `search_corpora.py` — bounded-поиск по корпусам (`status` / `sources` / `search "q" [--source X] [--limit N]`);
- `verify_clones.py` / `retry_cleanup.py` / `manifest_prune.py` / `links_prune.py` / `fetch_one.py` / `hf_snapshot_worker.py` — сопровождение;
- индекс содержимого: `knowledge_base/artifacts-index-2026-11-10.md`;
- каталог техник: `harness/TECHNIQUES.md`.

## 6. Тесты

```sh
python3 harness/lbp_checks_test.py            # 14/14
python3 harness/lbp_blitz.py --model TEST --dry --scenarios negq,giftcard,scam,bank
python3 prompt_injection_ctf/raw/sources/artifacts/search_corpora.py status
```

## 7. Грабли загрузок (Windows)

- длинные пути → `core.longpaths=true`; имена с ':' → `core.protectNTFS=false` (статус `cloned-partial`);
- 404-репо → git виснет на credential-промпте → `GIT_TERMINAL_PROMPT=0` + `stdin=DEVNULL`;
- HF-столлы → воркер-подпроцесс с таймаутом 900 s + bounded urllib-фолбэк; отдельные датасеты «прокляты» сетью (`skipped-network`).
