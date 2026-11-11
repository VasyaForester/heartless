# План дообучения под IPI Black 2026 (Indirect Prompt Injection)

Цель: закрыть разрыв между текущей базой (chat-экстракция, классические IPI) и реалиями доски:
агенты-инженеры 2026 с tool-guard'ами (проверка отправителя, conflict-detection, provenance-аудит).
«Дообучение» = RAG + дистилляция знаний в базу + оружейные шаблоны (локальный fine-tune LLM невозможен).

## Слой 1 — Литература и источники (вход) — ✅ ВЫПОЛНЕНО
1. **arXiv (расширенный охват)** ✅: 16 агентных запросов, манифест 428 → **766** статей; +24 новых полных текста (всего 90 PDF→txt); ключевые: Task-Tampering (2611.07640), Permitted-but-Unauthorized (2611.04086), CARI (2610.38799), TrustJev (2610.34826), CoSA (2610.35082), Log-To-Leak (2610.36108), «Position, Role or Label» (209k), NameTrap. Скрипт: `raw/sources/arxiv/fetch_arxiv_agentic.py`.
2. **Веб-источники** ✅: embracethered (RSS 233 поста → 98 релевантных → 12 полных текстов: Agentic ProbLLMs, Cross-Agent PrivEsc, AI Kill Chain, Devin, Kiro, DNS-exfil, OpenAI URL-safe, Agent Commander, Claude Code, Lethal Trifecta, Copilot RCE, Scary Skills) + simonwillison IPI-atom. `raw/sources/web/`.
3. **Синтез с эмпирикой** ✅: ND-005 + раздел в KB.

## Слой 2 — Дистилляция в базу (обработка) — ✅ ВЫПОЛНЕНО
1. ✅ `knowledge_base/agentic-ipi-2026.md` (классы: task-tampering, action-representation, CARI, self-config-write, обходы отказов; матрица под доску).
2. ✅ `novel_discoveries/ND-005-agentic-board-decision-frames.md` (доставка ✓; стены: conflict-report, identity-verify, per-chat рандом имён, self-config guard).
3. ✅ Переиндексация RAG (`scripts/rag_build.py`, фон) + обновлён `00_index.md`; 90 полных текстов в KB-доках.

## Слой 3 — Оружейные кандидаты (выход) — ✅ v6 ГОТОВЫ
1. ✅ `inputs/ipi-candidates-v6.md` + пейлоады `ipi-wb3s1-v6-{jira,slack}`, `ipi-wb3s2-v6-slack`:
   record-shaped (FRZ-118), action-listing, state-tampering, CARI-голос, subpattern-гигиена.
2. Калибровка: следующий ран — WB3S2 v6 (1 инъекция), затем WB3S1 v6 (пара); один механизм за ран.

## Метрика успеха
- Не «больше текстов», а: список механизмов с эмпирическим статусом (работает / проверено-мертво),
  и каждый следующий ран = проверка ровно одного класса (одно изменение за попытку).
