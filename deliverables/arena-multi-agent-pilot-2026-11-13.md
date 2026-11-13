# ARENA MULTI-AGENT PILOT — отчёт 2026-11-13

**Статус: работает сквозным циклом.** Механическая часть пилота (Kanban-конвейер ролей) выполнена и проверена дважды.

## Что операционно (команды)

```
# 1. Кейсфайл (детерминированный билдер, 3 режима: SPEC/HISTORY/EVIDENCE)
python3 tools/casefile.py banking-idor-exploit "Sand Ant Plus Ultra"

# 2. Карточки (доска arena-lab; воркерский профиль = gray-swan-hackathon-v2)
hermes kanban create "<title>" --assignee gray-swan-hackathon-v2 \
    --body-file tasks/<role>.md --workspace "dir:<абс.путь workspace>" \
    [--parent <id> ...] [--model ... / set-model <id> none для сброса]

# 3. Наблюдение
hermes kanban ls / show <id> / stats
docker нет — диспетчер живёт в gateway (PID 2552, автозапуск при Windows login)
```

Роли как карточки: ANALYST (FULL_HISTORY) + STRATEGIST (BLIND) + SCOUT параллельно → SKEPTIC (гейт новизны + спот-аудит → experiment-card JSON). Каждый воркер = свежая сессия (новый чат), изоляция контекста задаётся телом карточки.

## Результаты двух циклов (bank-SA, 13:17–13:26, ~4 мин/цикл, все на deepseek)

- Цикл 1 (t_9931e946/d26d2292/9d47c0cb/87b09602): все 4 карточки done. Выходы: casefiles/out-*.md + experiment-card-bank-sa.json.
- Цикл 2 (t_2aa0de25/96dc2091/3fe2393f/13312845): все 4 done. Выходы: casefiles/out2-*.md + experiment-card-bank-sa-v2.json.
- ANALYST: карта стадий подтверждена числами из loop-results (74/36/31; вызов достижим, раскрытие = session_scope/withholding).
- STRATEGIST (blind): 6 гипотез за 2 цикла, механизмы в основном близки к уже отбитым (id-обвязки, form-поле, multi-step карриовер). Полезность blind-режима низкая на этой паре — история сильнее любой слепой догадки.
- SCOUT: цикл 1 — выдумал example.com URL (проверка сработала: отбросить); цикл 2 — честно сообщил: **в профиле gray-swan-hackathon-v2 НЕТ инструментов web_search/web_extract**. Выход: scout-карточки назначать профилю `default` (там веб есть) либо включить web в конфиг профиля.
- SKEPTIC: цикл 1 — слишком мягкий (passed на «обёртки»); цикл 2 (после ужесточения) — вынес passed по гипотезе FAQ-контекста (novelty_check со ссылкой на tried-index, но схема JSON неполная — не хватает expected_observation/execution/audit).

## Известные ограничения и фиксы для цикла 3

1. Профили-специалисты (arena-analyst/strategist/skeptic/scout) созданы, но БЕЗ креденшелов (auth.json) — воркеры падают «Kanban owner refused». Решение пилота: задачи назначены рабочему профилю gray-swan-hackathon-v2. Для ролевых профилей нужно разовое разрешение на копирование auth.json.
2. Scout без веба → назначение на `default` или включение web-инструментов в профиль.
3. Skeptic: требовать строго полную схему experiment-card (валидировать отсутствие полей → failed).
4. Стратег blind на bank-SA даёт слабые идеи → для этой пары ценнее FULL_HISTORY-ветка; blind применять к стенам без истории.

## Решение по experiment-card-bank-sa-v2

Гипотеза FAQ-контекста НЕ поставлена в арену: механизм близок к id-обвязкам (десятки отбитых), энергия аккаунта расходуется экономно. Карточка лежит в очереди casefiles/experiment-card-bank-sa-v2.json как кандидат при следующем благоприятном окне.

## Стоимость

Весь пилот (8 воркер-сессий) — на deepseek (профильный дефолт), без модель-оверрайдов, без MoA. Дорогие модели не использовались (по указанию пользователя).
