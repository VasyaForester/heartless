#!/usr/bin/env bash
# Loop watchdog: keeps harness/loop.py alive without a human.
# Rule: the driver must never "finish a wave and wait" — if it dies, this restarts it.
# Runs from cron every 5-10 min. Silent when healthy (empty stdout = no notification).
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1

HB="artifacts/loop-heartbeat.json"
LOG="artifacts/loop-watchdog.log"
PIDFILE="artifacts/loop.pid"
# ВАЖНО (правило 57): пауза автопилота. Если файл-флаг существует — ничего не делаем.
# Автопилот не должен работать одновременно с живой сессией (общий Chrome-таб → окна switch + мусор в чатах).
[ -f "artifacts/loop.paused" ] && exit 0
# tab-id НЕ хардкодить: он живёт только до рестарта браузера (инцидент со старым F770…)
TARGET="${CHAT_TARGET:-$(python3 harness/pick_target.py 2>/dev/null)}"
[ -z "${TARGET:-}" ] && { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog: no LBP tab (pick_target empty), skip" >> "$LOG"; exit 0; }
MAX_AGE="${LOOP_MAX_AGE:-600}"   # heartbeat older than 10 min = considered stuck/dead
MAX_HOURS="${LOOP_MAX_HOURS:-12}"

now=$(date +%s)
alive=0
if [ -f "$PIDFILE" ]; then
  pid=$(cat "$PIDFILE" 2>/dev/null | tr -d '[:space:]')
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then alive=1; fi
fi
# fallback: look for the driver process by command line
if [ "$alive" = "0" ]; then
  if ps -ef 2>/dev/null | grep -v grep | grep -q "harness/loop.py"; then alive=1; fi
fi

age=999999
if [ -f "$HB" ]; then
  mt=$(stat -c %Y "$HB" 2>/dev/null || stat -f %m "$HB" 2>/dev/null || echo 0)
  age=$(( now - mt ))
fi

if [ "$alive" = "1" ] && [ "$age" -lt "$MAX_AGE" ]; then
  exit 0   # healthy: say nothing
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog: alive=$alive heartbeat_age=${age}s -> restarting driver" >> "$LOG"
# kill a stuck driver before starting a fresh one
if [ "$alive" = "1" ]; then
  pkill -f "harness/loop.py" 2>/dev/null || true
  sleep 2
fi
nohup python3 harness/loop.py --target "$TARGET" --max-hours "$MAX_HOURS" \
  >> "artifacts/loop.out" 2>&1 &
echo $! > "$PIDFILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog: started pid $(cat "$PIDFILE")" >> "$LOG"
