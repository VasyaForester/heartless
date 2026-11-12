# ПАУЗА 2026-11-12 ~15:50 — приказ участника

**Статус: автопилот LBP ОСТАНОВЛЕН по приказу участника («прервись, не решай; запущу параллельного агента, который протестирует новый подход»).**

## Что остановлено
- Драйвер автопилота `harness/loop.py` (auto-лейн) — остановлен (graceful exit по `restart.requested`).
- Флаг паузы: `artifacts/lane-auto/loop.paused` (watchdog НЕ перезапускает, пока файл на месте).
- Кроны на паузе: `pg-loop-watchdog` (e32801868769) и `lbp-autopilot-supervisor` (cf2a52e8efa0).
- Энергия НЕ расходуется: новые пробы не запускаются.

## Что НЕ трогать (живая инфраструктура — в прошлый раз их удаление сломало систему)
- `tools/loop_watchdog.sh`, `tools/lane_auto.sh`, `tools/run1.sh`
- `~/AppData/Local/hermes/scripts/loop_watchdog.sh` (шим)
- `harness/loop.py`, `harness/lbp.py`, `RULES.md`, `datasets/lbp/*`, `inputs/lbp-*`
- Браузер auto-лейна (Chrome CDP 9224) — оставлен как есть; окна не открываются.

## Как возобновить (когда участник скажет)
1. `rm -f artifacts/lane-auto/loop.paused artifacts/lane-auto/restart.requested`
2. Возобновить кроны: `pg-loop-watchdog` (e32801868769), при необходимости `lbp-autopilot-supervisor` (cf2a52e8efa0).
3. Ручной старт: из workspace `LOOP_LANE=auto bash tools/lane_auto.sh` (или подождать крон ≤10 мин).
4. Либо просто сказать ассистенту «продолжай» — он сделает всё это сам.

## Контекст для параллельного агента
- Доска LBP: 12/20 (scam 4/4, refund 4/4, giftcard 1/4, negq 1/4, bank 2/4). Энергия на момент паузы ~450 (не тратится).
- Сабмиты: политика `smart` (`LBP_SUBMIT_POLICY`): сабмит только при готовности/≥1 пройденном критерии, кулдаун 900с/пара, ≤8/час; отказы не судятся. Ручной сабмит: `harness/lbp.py submit --scenario <sid>`.
- Правила проекта: `RULES.md` (важны 53–61). Правило 61(б): не удалять живые файлы инфраструктуры.
- Пробные запуски: `python3 harness/lbp.py repeat --scenario <sid> --model "<Model>" --input <файл> [--submit]`.
