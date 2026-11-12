# Benchmark-derived classes → LBP / PG scenarios (2026-11-12)

Маппинг: какой бенчмарк/датасет даёт какие классы для харнесса. Это не «пакеты payload»,
а источник классов, калибровки судьи и defensive-чеклистов.

## Agent security & utility

- **InjecAgent** → banking-idor-exploit / negative-quantity-exploit
- **AgentDojo** → banking-idor-exploit / double-refund
- **Agent-SafetyBench** → scam-retail / christmas-giftcard-scam / banking-idor-exploit
- **AgentHarm** → scam-retail / christmas-giftcard-scam
- **ASB** → scam-retail / banking-idor-exploit
- **ToolEmu** → banking-idor-exploit / negative-quantity-exploit
- **tau2-bench** → utility-baseline
- **AgentLAB** → utility-baseline
- **ST-WebAgentBench** → utility-baseline
- **os-harm** → utility-baseline
- **terminal-bench** → utility-baseline
- **TheAgentCompany** → utility-baseline
- **Vakra** → utility-baseline
- **RE-Bench** → utility-baseline

## Code / cyber security

- **CWEval** → code-baseline
- **AICGSecEval** → code-baseline
- **SecRepoBench** → code-baseline
- **SecureAgentBench** → code-baseline
- **SEC-bench** → code-baseline
- **redcode** → code-baseline
- **baxbench** → code-baseline
- **PrimeVul** → code-baseline
- **cybench** → code-baseline
- **cve-bench** → code-baseline

## Multimodal safety

- **JailBreakV_28K** → image-baseline
- **MM-SafetyBench** → image-baseline
- **UnsafeBench** → image-baseline
- **VLSBench** → image-baseline
- **MSTS** → image-baseline
- **holisafe-bench** → image-baseline
- **OmniSafeBench-MM** → image-baseline

## Prompt injection & tooling

- **PyRIT** → payload-generator
- **AI-Infra-Guard** → defensive-checklist
- **DoomArena** → agent-attack-env
- **MCPSafety** → mcp-baseline
- **secure-agent-playbook** → defensive-checklist
- **OWASP secure-agent-playbook** → defensive-checklist
- **ZJU-SEC Readings** → defensive-checklist
- **awesome-prompt-injection** → payload-generator
- **Awesome-LLM-Safety** → defensive-checklist
- **awesome-ai-security** → defensive-checklist
- **Lakera Backbone Breaker** → payload-generator
- **USENIX Security 2026 (Ling)** → judge-calibration
- **PyRIT** → payload-generator

## Stored-value / gift-card (из отдельного подбора 2026-11-12)

- **Gao & Wu 2026** → christmas-giftcard-scam
- **Kled Scam Marketplace Listings** → christmas-giftcard-scam / scam-retail
- **ELFW-2031** → christmas-giftcard-scam
- **TXD-22** → judge-calibration
- **TROVE** → judge-calibration

## Как использовать

1. `agent-security` и `stored-value` — источник классов для LBP-проб; не копировать payload дословно.
2. `code-baseline` — отдельная ось; подключать только если сценарий PG действительно про код/терминал.
3. `image-baseline` — мультимодальные сценарии PG; для LBP не смешивать.
4. `utility-baseline` — регрессия полезности; не считать security-победой.
5. `defensive-checklist` — отдельная ось «безопасное поведение»; не оптимизировать её вместе с CTF-счётом.