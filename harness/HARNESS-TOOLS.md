# HARNESS-TOOLS — практический справочник (обновлено 2026-11-06)

Инструменты обвязки поверх штатного адаптера (`harness/hackathon.py arena ...`, доки — `ENGINE.md`).
Все команды — из `workspace`.

## Инструменты

| Инструмент | Назначение | Ключевые примеры |
|---|---|---|
| `harness/farm.py` | Батч-прогон по моделям с чекпойнтом/резюмом, авто-judge на comply | `--dry-run` (только select/bind/inspect — безопасный тест), `--sweep` (свип после раунда), верификация выбора `selected+verified`, авто-retry bind при «model is unknown»; перед судейским шагом УДАЛЯЕТ старый judge-файл (stale-guard 2026-11-10: отсутствие файла = unknown, а не чужой вердикт; требовал `import os` — NameError на os.remove исправлен 2026-11-11) |
| `tools/pg_*.py` | PG-сессия (2026-11-10): ридеры, билдеры, реестр пар, захват eval | `pg_snap.py FILE models\|inspect`; `show_msgs.py FILE`; `pg_build_s2.py` (F10/p6c/p6d payloads); `pg_build_s4.py --mode tag\|u2028`; `pg_pairs.py` (реврайт `datasets/proving-ground/pairs.jsonl`); `pg_eval_capture.py` (полный текст страницы сабмита + SEE EVALUATION) |
| `harness/arena_heal.py` | Авто-починки: stale scope → rebind+retry; «verdict is already visible» → CONTINUE + retry; select-fresh | `judge`, `click`, `clear-verdict`, `select-fresh`; журнал `attempts/heal-log.jsonl` |
| `harness/classify_response.py` | Классы ответов: `refuse_template` / `empty_response` / `blocked_filter` / `comply_full` / `comply_short` + pre-judge эвристики | `--batch "artifacts/farm-*-send-result.json"` |
| `harness/arena_chats.py` | Модалка чатов/сабмишенов → JSON | Формат: `STATUS\nTODAY h:mmPM\n<превью>\n(Сцен.)\n·\n<Модель>`; номер сценария опционален (`(Easy) …` и `3. (Hard) …`); modal-URL сам выставляет нужную вкладку (`chatsTab` больше не протекает); для не-PG досок новый флаг `--board-substr <slug>` (дефолт proving-ground; для LBP — `lucky-break-payday`); таб должен стоять в чате (URL с `chatId`); `modal_url` канонизирует URL (challenge-адрес + `chatId` собираются заново, кривой URL → ошибка БЕЗ навигации — фикс 404-класса №2, 2026-11-10) |
| `harness/verdict_sweep.py` | Сверка pending/unknown вердиктов в чекпойнт ферма | **ОБЯЗАТЕЛЬНО** `--scenario-id` (иначе зачёт модели в ДРУГОМ сценарии = ложный апдейт — ловили на OG/BSE) |
| `harness/chat_ops.py` | Единый CLI для диалогов | `find` (строки+chatId), `open`, `meta` (model/banner/judgeDisabled), `read` (дамп текста), `followup` (turn-2 в тот же чат), `judge` (с привязкой к модели чата); `--bootstrap-chat-id` если в URL нет chatId; `evaljs`/проба теперь требуют явный `--target` (дефолт-match мог читать чужую вкладку — инцидент 2026-11-10: проба соседа-PG) |
| `harness/pending.py` | Реестр ожиданий `artifacts/pending_ledger.json` + backoff-опрос | `add`, `list`, `due`, `poll --target T` (banner чата + SUBMITTED), `resolve`; backoff 15s→1h; `expired` ≠ провал |
| `harness/verdict_verify.py` | Глобальная сверка SUBMITTED ↔ ВСЕ чекпойнты ↔ журнал ↔ леджер | по умолчанию read-only; `--apply` пишет ckpt-ы, журнальные корректировки (same attemptId), леджер; overdub-защита (одна строка → один чекпойнт) |
| `harness/scenario_filters.py` | Общая карта фильтров сценариев + stem-hints для кастомных имён чекпойнтов | используют `verdict_sweep` / `verdict_verify` / `pending` |
| `harness/wave_scan.py` | Инвентаризация волн → `artifacts/waves-scan.json` + `waves-map.md` | запускать только при простое (водит тот же таб); `--waves 2-26`; switch-wave.mjs теперь с JS-фолбэками для React-поповера |
| `harness/lbp_plan.py` | Планировщик LBP (дерево решений): категория → приоритет стратегий → план прогона; read-only | `--all` / `--scenario X [--model M]` / `--check` / `--principles`; док — `DECISION-TREE.md` |
| `harness/lbp_eval_row.py` | Захват receipt по КОНКРЕТНОМУ сабмиту (не только новейшему) | `--list` (submissionId-линки модалки), `--sid <id>` (прямой URL панели оценки), `--row N`; перед снятием — `lbp.py reload`, если старая панель могла остаться открытой |
| `tools/inspect_texts.py` | Быстрый текст из inspect-дампа | `--filter criteria,chat --max 500` |
| `tools/pptx_dump.py` / `tools/fill_pptx.py` | Разбор и заполнение .pptx | см. навык `presentation-decks` |

## Типовые рецепты

**Раунд ферма:** dry-run (1 модель) → реальный прогон (`--judge-policy comply`, `--pause 20`) → `--sweep` (или отдельно `verdict_sweep.py`) → записи в журнал (`hackathon.py record`).

**Резюм pending:** `python3 harness/pending.py poll --target T` (due-элементы: banner чата и/или SUBMITTED) → затем полная сверка `python3 harness/verdict_verify.py --target T --apply`.

**Вердикт-слежение за свежим сабмитом (LBP/любая доска):** `python3 harness/pending.py add --model "<M>" --scenario <slug> [--chat-id <id>]` → циклический `poll` с брейком по первому резолву: `OUT=$(python3 harness/pending.py poll --target T --bootstrap-chat-id <id>); echo "$OUT"; echo "$OUT" | grep -q '"resolved": \[{' && break; sleep 240` (лог в `cache/probe/verdict-watch-*.log`). Path 1 — баннер чата (нужен `chatId`), path 2 — SUBMITTED-список. Пока вердикт не пришёл — не ресабмитить пару.

**Turn-2 в тот же чат:** `python3 harness/chat_ops.py followup --chat-id <id> --scenario-id <slug> --file inputs/...` (сам открывает чат, биндит scope на модель чата, шлёт один раз); суд — отдельно `chat_ops.py judge --chat-id <id> --scenario-id <slug>`.

**После resume farm сам закрывает stale-модалку** (`modal=` в URL → навигация на `?behaviorId=`), плюс пишет `scenario`/`track` в чекпойнт и авто-`pending add` при `judge: pending/unknown`.

**Критерии сценария:** `python3 harness/hackathon.py arena show-criteria --target T --out artifacts/criteria-X.json` — самодостаточно, НЕ кликать относительные селекторы вида `div:nth-of-type(3) > button:nth-of-type(2)` из inspect: они матчат первый элемент с таким путём (случайно попали в аватар профиля). Для полного текста элемента — `arena read --target T --selector CSS`.

**Модель «unknown» после навигации:** `arena models` → `arena select-model` (через другую модель и обратно при повторе) → rebind. В farm.py это уже встроено.

**Застрявший вердикт:** `arena_heal.py clear-verdict` (ищет кнопку CONTINUE по короткому тексту) → повторный judge.

**Зависший/пустой свип:** проверить, не показывает ли вкладка Vercel-проверку («Контрольная точка безопасности») — повторить через паузу.

**Планирование LBP-раунда:** `python3 harness/lbp_plan.py --all` — план по всей доске: по каждой паре категория (target kind × класс модели), RUN/PARK и готовые команды прогона; регламент — `harness/DECISION-TREE.md`. После прогона — обновить `pairs.jsonl` и `decision-tree.json` (новые исчерпанные классы → spent/PARK).

## State-модель (важно)

- Вердикт-баннер может рендерить ТЕКУЩУЮ выбранную модель поверх старых вердиктов — истина в списке SUBMITTED (status+time+model) и бейджах BROKEN.
- `pending` ≠ провал: не ресабмитить, сверять свипом позже.
- После каждой навигации/смены модели — rebind scope (`Scope is stale` лечится heal-ом).
- Дубли отправок запрещены; чекпойнт ферма исключает повторные send (кроме `--retry`).
