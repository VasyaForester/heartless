# Чекпойнт — 2026-11-10 (режим: пауза активных проб до ротации)

## Доска Lucky Break: Payday
- **4/5 сценариев · 5/20 breaks** (giftcard CT, refund CT, scam CT, bank CT, bank YK).
- Ротация: 0 изменений за день (тики #1–#4). Следующий шаг при ротации: `python3 harness/lbp_blitz.py --model "<новая модель>"` — прогонит 4 рецепта (giftcard / scam / bank / negq-лестницу) с авто-сабмитами.
- Все 15 незакрытых пар = задокументированные стены с цитатами отказов (см. `datasets/lbp/pairs.jsonl`, `model_matrix.md`, `corpus-classes-2026-11-10.md`).
- Инструкция участника: **активные пробы на паузе до ротации/новой волны** (записано в CLAUDE.md).

## Что наработано сегодня (2026-11-10)
- Многоходовые кампании: bank×DW warmup (мок заранее закрыл), negq×CT/SA лестницы «заказ → фикс знака» (заказ исполняется! `purchase(cost:10, quantity:100)`; знак — стена модели).
- Новые классы против negq: stock-adjust, разговор на суахили (MultilingualJailbreak) — отбито семантически; code-spec (CodeAttack-стиль) — отбито.
- Карта покрытия 16 классов ChatGPT + каталог 19 техник PromptSecurity — в `datasets/lbp/corpus-classes-2026-11-10.md`.
- Харнесс: `lbp.py repeat/export`, `lbp_blitz.py` (4 рецепта), `lbp_roster.py` (сторож), receipts/snaпшоты в `artifacts/`.

## Фон (не трогает доску)
- Закачка артефактов: `proc_39bb677f2177` (сейчас ~[20/50]); всего 40+ репо и датасетов уже на диске (`raw/sources/artifacts/`, индекс — `knowledge_base/artifacts-index-2026-11-10.md`).
- Известные хвосты: llmail HF dataset — `skipped-network`; PVDetector — взят вручную (1.3GB ✓).

## Следующие триггеры
1. Ротация ростера → blitz 4×N.
2. Твой ввод (идеи/ChatGPT-раунд) → точечные новые классы.
3. ~~Завершение закачки~~ → ВЫПОЛНЕНО.

## Финал закачки (14:45) и собранный харнесс

**Закачка остановлена по таймеру.** Итог: **63 уникальных артефакта** — 45 репо (+2 partial) + HF-датасеты (JailbreakDB 598МБ, babel-briefings 441МБ, tensor-trust 133МБ, JBB, ipi_arena_attacks, PromptSecurity-Eval partial…); хвост ~20 позиций — по запросу (`fetch_selected.py`).

**Последние жемчужины:** `ipi_arena_attacks` (95 реальных атак арены в формате подмены системного промпта — НОВЫЙ класс для наших стен), `task-tampering-prompt-injection` (90 кейсов + 1433 варианта — первоисточник нашей refund-темы), MemHarmBench, INFUSE.

**Харнесс (собран из всего):**
- доска: `lbp.py` (repeat/export/eval), `lbp_blitz.py` (4 рецепта), `lbp_roster.py`, checks/contracts/events/report;
- слои-доки: `harness/LBP.md` (наш слой), `harness/TECHNIQUES.md` (каталог 19 техник), `harness/ENGINE.md` (упакованный);
- корпуса: `search_corpora.py` (поиск по всем корпусам), `fetch_selected.py` (точечный добор), полный тулчейн fetch/verify/prune;
- данные: `datasets/lbp/*` + `knowledge_base/artifacts-index-2026-11-10.md` + `corpus-classes-2026-11-10.md`;
- тесты: 14/14 валидаторов, blitz dry 4/4, компиляция чистая.
