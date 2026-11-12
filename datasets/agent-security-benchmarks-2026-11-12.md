# Agent-security benchmarks & datasets — каталог (2026-11-12)

Источников: 61. Уже упоминаются в харнессе: 13. Новых: 48. HTTP 200: 61/61.

## Дополнение 2026-11-12 — защитные механизмы и оценка tool-using agents (8 работ)

Не повторяют список выше. Проверка ссылок 2026-11-12: 9/10 HTTP 200; MDPI отдаёт 403 curl (Cloudflare), текст получен через web-reader. Это исследования защит/оценки, не инструкции по публикации мошеннических объявлений.

1. AIRGuard: Guarding Agent Actions with Runtime Authority Control (2026) — https://arxiv.org/abs/2605.28914 — runtime enforcement; ASR на Claude Sonnet 4.6 36.3% → 5.5%; код: https://github.com/Sophie508/AIRGuard
2. PolicyGuide: From Guarding One Action to Guiding the Whole Workflow (2026) — https://arxiv.org/abs/2608.19861 — workflow-level policy verification; Pass⁴ 0.42 → 0.62; GPT-5.4, Claude Sonnet 4.6, Gemini 2.5 Pro.
3. AgentAbstain (NeurIPS 2026 Oral) — https://agentabstain.github.io/ — 17 frontier-моделей, 263 парных сценария, 42 среды, 541 инструмент; лучший act-or-abstain 59.5%.
4. Scaling Misuse Detection with Self-Assessment (Anthropic, October 2026) — https://safeguards.anthropic.com/2026/self-assessment/ — Claude Fable 5: 78% потенциально вредных диалогов, 94% высокоприоритетных при 1% false positives.
5. PolicyGuard: A Dialogue-Grounded Sub-Agent Verifier (2026) — https://arxiv.org/abs/2606.29225 — контекстная проверка политик по всей истории диалога; GPT-5.4, Claude Sonnet 4.6, Gemini 2.5 Pro.
6. Evaluating Indirect Prompt Injection Defenses in Tool-Using LLM Agents (2026) — https://www.mdpi.com/2073-431x/15/9/570 — GPT-5.4, GPT-5.4-mini, Claude Sonnet 4.6; две независимые репликации, execution traces; dataset: https://doi.org/10.5281/zenodo.20731176
7. Efficient LLM Safety Evaluation through Multi-Agent Debate (EMNLP 2026) — https://aclanthology.org/2026.emnlp-main.76/ — 11 100 человеческих разметок; multi-agent judge на малых моделях, качество близко к GPT-4o.
8. WorkBench Revisited: Workplace Agents Two Years On (2026) — https://arxiv.org/abs/2606.13715 — 24 модели, включая GPT-5.5 и Claude Opus 4.8; 690 задач, 26 инструментов, оценка реальных побочных эффектов.

## Новое (чего ещё нет в базе)

- https://github.com/SaFo-Lab/JailBreakV_28K — HTTP 200
- https://huggingface.co/datasets/Foreshhh/vlsbench — HTTP 200
- https://huggingface.co/datasets/felfri/MSTS — HTTP 200
- https://huggingface.co/datasets/Advait-s06/safe-vs-unsafe-image-edits — HTTP 200
- https://huggingface.co/datasets/yiting/Self-harm_Dataset — HTTP 200
- https://huggingface.co/datasets/Parveshiiii/AI-vs-Real — HTTP 200
- https://github.com/ChinaZhangPeng/Violence-Image-Dataset — HTTP 200
- https://huggingface.co/datasets/mrm8488/ImageNet1K-val — HTTP 200
- https://huggingface.co/datasets/biecho/hateful_memes — HTTP 200
- https://huggingface.co/datasets/yiting/UnsafeBench — HTTP 200
- https://huggingface.co/datasets/etri-vilab/holisafe-bench — HTTP 200
- https://github.com/isXinLiu/MM-SafetyBench — HTTP 200
- https://www.usenix.org/conference/usenixsecurity26/presentation/ling — HTTP 200
- https://lakera.ai/blog/the-backbone-breaker-benchmark — HTTP 200
- https://github.com/TanqiuJiang/AgentLAB — HTTP 200
- https://github.com/segev-shlomov/ST-WebAgentBench — HTTP 200
- https://github.com/tml-epfl/os-harm — HTTP 200
- https://github.com/harbor-framework/terminal-bench — HTTP 200
- https://github.com/TheAgentCompany/TheAgentCompany — HTTP 200
- https://github.com/IBM/vakra — HTTP 200
- https://github.com/METR/RE-Bench — HTTP 200
- https://arxiv.org/abs/2512.15163 — HTTP 200
- https://github.com/Co1lin/CWEval — HTTP 200
- https://github.com/Tencent/AICGSecEval — HTTP 200
- https://arxiv.org/abs/2410.11096 — HTTP 200
- https://github.com/ai-sec-lab/SecRepoBench — HTTP 200
- https://github.com/iCSawyer/SecureAgentBench — HTTP 200
- https://github.com/SEC-bench/SEC-bench — HTTP 200
- https://github.com/ai-secure/redcode — HTTP 200
- https://baxbench.com — HTTP 200
- https://github.com/DLVulDet/PrimeVul — HTTP 200
- https://github.com/andyzorigin/cybench — HTTP 200
- https://github.com/uiuc-kang-lab/cve-bench — HTTP 200
- https://arxiv.org/abs/2506.02548 — HTTP 200
- https://arxiv.org/abs/2303.06729 — HTTP 200
- https://arxiv.org/abs/2412.20787 — HTTP 200
- https://github.com/ServiceNow/DoomArena — HTTP 200
- https://github.com/xjzzzzzzzz/MCPSafety — HTTP 200
- https://github.com/usnistgov/agentdojo-inspect — HTTP 200
- https://arxiv.org/abs/2601.03699 — HTTP 200
- https://github.com/tencent/AI-Infra-Guard — HTTP 200
- https://arxiv.org/abs/2602.20708 — HTTP 200
- https://openreview.net/forum?id=PFbt5pWWh7 — HTTP 200
- https://github.com/ZJU-SEC/Readings — HTTP 200
- https://github.com/OWASP/secure-agent-playbook — HTTP 200
- https://arxiv.org/abs/2605.17986 — HTTP 200
- https://github.com/ydyjya/Awesome-LLM-Safety — HTTP 200
- https://github.com/8kSec/awesome-ai-security — HTTP 200

## Полный каталог

### Multimodal safety / jailbreak datasets

1. https://github.com/SaFo-Lab/JailBreakV_28K — HTTP 200 — NEW
2. https://huggingface.co/datasets/Foreshhh/vlsbench — HTTP 200 — NEW
3. https://huggingface.co/datasets/felfri/MSTS — HTTP 200 — NEW
4. https://huggingface.co/datasets/Advait-s06/safe-vs-unsafe-image-edits — HTTP 200 — NEW
5. https://huggingface.co/datasets/yiting/Self-harm_Dataset — HTTP 200 — NEW
6. https://huggingface.co/datasets/Parveshiiii/AI-vs-Real — HTTP 200 — NEW
7. https://github.com/ChinaZhangPeng/Violence-Image-Dataset — HTTP 200 — NEW
8. https://huggingface.co/datasets/mrm8488/ImageNet1K-val — HTTP 200 — NEW
9. https://huggingface.co/datasets/biecho/hateful_memes — HTTP 200 — NEW
10. https://huggingface.co/datasets/yiting/UnsafeBench — HTTP 200 — NEW
11. https://huggingface.co/datasets/etri-vilab/holisafe-bench — HTTP 200 — NEW
12. https://github.com/isXinLiu/MM-SafetyBench — HTTP 200 — NEW

### USENIX Security 2026

13. https://www.usenix.org/conference/usenixsecurity26/presentation/ling — HTTP 200 — NEW

### Agent security & utility benchmarks

14. https://github.com/uiuc-kang-lab/InjecAgent — HTTP 200 — known
15. https://github.com/agiresearch/ASB — HTTP 200 — known
16. https://github.com/ryoungj/toolemu — HTTP 200 — known
17. https://lakera.ai/blog/the-backbone-breaker-benchmark — HTTP 200 — NEW
18. https://huggingface.co/datasets/ai-safety-institute/AgentHarm — HTTP 200 — known
19. https://github.com/thu-coai/Agent-SafetyBench — HTTP 200 — known
20. https://github.com/sierra-research/tau2-bench — HTTP 200 — known
21. https://github.com/TanqiuJiang/AgentLAB — HTTP 200 — NEW
22. https://arxiv.org/abs/2506.15740 — HTTP 200 — known
23. https://arxiv.org/abs/2507.20526 — HTTP 200 — known
24. https://github.com/facebookresearch/wasp — HTTP 200 — known
25. https://github.com/segev-shlomov/ST-WebAgentBench — HTTP 200 — NEW
26. https://github.com/tml-epfl/os-harm — HTTP 200 — NEW
27. https://github.com/harbor-framework/terminal-bench — HTTP 200 — NEW
28. https://github.com/TheAgentCompany/TheAgentCompany — HTTP 200 — NEW
29. https://github.com/IBM/vakra — HTTP 200 — NEW
30. https://github.com/METR/RE-Bench — HTTP 200 — NEW

### Code / cyber security benchmarks

31. https://arxiv.org/abs/2512.15163 — HTTP 200 — NEW
32. https://github.com/Co1lin/CWEval — HTTP 200 — NEW
33. https://github.com/Tencent/AICGSecEval — HTTP 200 — NEW
34. https://arxiv.org/abs/2410.11096 — HTTP 200 — NEW
35. https://github.com/ai-sec-lab/SecRepoBench — HTTP 200 — NEW
36. https://github.com/iCSawyer/SecureAgentBench — HTTP 200 — NEW
37. https://github.com/SEC-bench/SEC-bench — HTTP 200 — NEW
38. https://github.com/ai-secure/redcode — HTTP 200 — NEW
39. https://baxbench.com — HTTP 200 — NEW
40. https://github.com/DLVulDet/PrimeVul — HTTP 200 — NEW
41. https://github.com/andyzorigin/cybench — HTTP 200 — NEW
42. https://github.com/uiuc-kang-lab/cve-bench — HTTP 200 — NEW
43. https://arxiv.org/abs/2506.02548 — HTTP 200 — NEW
44. https://arxiv.org/abs/2303.06729 — HTTP 200 — NEW
45. https://arxiv.org/abs/2412.20787 — HTTP 200 — NEW

### Agent security environments

46. https://github.com/ServiceNow/DoomArena — HTTP 200 — NEW
47. https://github.com/xjzzzzzzzz/MCPSafety — HTTP 200 — NEW
48. https://github.com/ethz-spylab/agentdojo — HTTP 200 — known
49. https://github.com/usnistgov/agentdojo-inspect — HTTP 200 — NEW
50. https://github.com/jiaxiaojunQAQ/OmniSafeBench-MM — HTTP 200 — known
51. https://arxiv.org/abs/2601.03699 — HTTP 200 — NEW

### Tooling, frameworks & awesome lists

52. https://github.com/microsoft/PyRIT — HTTP 200 — known
53. https://github.com/tencent/AI-Infra-Guard — HTTP 200 — NEW
54. https://arxiv.org/abs/2602.20708 — HTTP 200 — NEW
55. https://openreview.net/forum?id=PFbt5pWWh7 — HTTP 200 — NEW
56. https://github.com/ZJU-SEC/Readings — HTTP 200 — NEW
57. https://github.com/OWASP/secure-agent-playbook — HTTP 200 — NEW
58. https://github.com/Joe-B-Security/awesome-prompt-injection — HTTP 200 — known
59. https://arxiv.org/abs/2605.17986 — HTTP 200 — NEW
60. https://github.com/ydyjya/Awesome-LLM-Safety — HTTP 200 — NEW
61. https://github.com/8kSec/awesome-ai-security — HTTP 200 — NEW

## Что с этим делать в harness

- InjecAgent / AgentDojo / Agent-SafetyBench — сценарии indirect prompt injection для Proving Ground и LBP; использовать как генератор классов, не как готовые payload.
- AgentHarm / Agent-SafetyBench — многошаговые вредоносные задачи; калибровать judge и failure taxonomy, не смешивать с utility.
- tau2-bench / terminal-bench / TheAgentCompany — utility-метрики; отдельная ось оценки, не security.
- CWEval / SecRepoBench / SEC-bench / cybench / cve-bench / PrimeVul — код-безопасность; для сценариев с кодом/терминалом.
- UnsafeBench / MM-SafetyBench / JailBreakV_28K / OmniSafeBench-MM — мультимодальные сценарии; для image-сценариев PG.
- PyRIT / AI-Infra-Guard / DoomArena — инструменты атаки и сканирования; генерировать пробы, не копировать вердикты.
- OWASP secure-agent-playbook — defensive-чеклист для отчёта и для отдельной оси «безопасное поведение».
- Kled / ELFW-2031 (из прошлого списка) — проверка продавца/площадки; для gift-card class.