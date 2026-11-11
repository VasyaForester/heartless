# Checkpoint — 2026-11-07 (вечер): harness-спринт завершён

- Состояние: **внешние отправки на паузе**; локальные работы спринта выполнены и проверены (read-only).
- Трекер журнала: см. `hackathon.py summary`; **Zinc plane ACCEPTED** добавлен как подтверждённая пара
  (`w6-plane-hijacking-zinc-followup`, eventId `b4c3c626-74fb-4e38-b21c-2e0dd28f130d`).

## Сделано в спринте (P0 по итогам обсуждения с ChatGPT-рекомендациями)

1. `harness/chat_ops.py` — единый CLI: `find | open | meta | read | followup | judge`.
   Проверено на живом чате: meta (model/banner), find (chatId-строки, pairing_ok=true).
2. `harness/pending.py` — реестр ожиданий `artifacts/pending_ledger.json`:
   `add | list | due | poll | resolve`; backoff 15s → 1m → 5m → 15m → 1h; `expired` ≠ провал.
   Засеян: pend-0001 Zinc (found/ACCEPTED), pend-0002 SandE plane (waiting, без chatId).
3. `harness/verdict_verify.py` — сверка SUBMITTED ↔ чекпойнты ↔ журнал ↔ леджер, `--apply`.
   Первый прогон: 7 корректировок (plane v1/v1b, vaccine-id2), 0 orphan, overdub-защита сработала.
4. `harness/farm.py` — конверт `send_intent` (UNCERTAIN_SEND на resume, `--mark-sent`),
   авто-`pending add` на `judge: pending/unknown`, запись `scenario`/`track` в чекпойнт.
5. `harness/arena_chats.py` — фикс формата строк модалки (номер сценария опционален: `(Easy) …`)
   и фикс modal-URL (`chatsTab`/`chatPage` вычищаются и выставляются принудительно).
6. `harness/scenario_filters.py` — общая карта фильтров + stem-hints для кастомных имён чекпойнтов.
   `verdict_sweep.py` переведён на общий модуль.

## Наблюдения на момент паузы

- Zinc botox chat `6aef4271b94f306e8be725b3` — NOT SUBMITTED (кандидат на суд после резюма).
- SandE plane — вердикт ещё не виден в SUBMITTED (pend-0002, backoff опрос).
- Не смапплены stem-подсказками: `s1-*`, `s3-*`, `s4-*`, `c2-*`, `c3-*` (добавить при знании их сценариев).
