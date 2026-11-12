#!/usr/bin/env bash
# Loop watchdog: keeps harness/loop.py alive without a human.
# Rule: the driver must never "finish a wave and wait" — if it dies, this restarts it.
# Runs from cron every 10 min. Silent when healthy (empty stdout = no notification).
#
# ЛЕЙНЫ (правило 57): main = живая сессия (CDP 9223), auto = изолированный автопилот (CDP 9224,
# отдельный Chrome-профиль browser-data-auto). Каждый лейн имеет свою директорию состояния.
# Автопилот НЕ должен работать на порту живой сессии. Пауза лейна = файл <state>/loop.paused.
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1

LANE="${LOOP_LANE:-auto}"
case "$LANE" in
  auto) export HACKATHON_CDP_URL="${HACKATHON_CDP_URL:-http://127.0.0.1:9224}" ; STATE_DIR="artifacts/lane-auto" ;;
  main) export HACKATHON_CDP_URL="${HACKATHON_CDP_URL:-http://127.0.0.1:9223}" ; STATE_DIR="artifacts/lane-main" ;;
  *)    echo "watchdog: unknown LOOP_LANE='$LANE' (expected auto|main)" >&2; exit 2 ;;
esac
mkdir -p "$STATE_DIR"
HB="$STATE_DIR/loop-heartbeat.json"
LOG="$STATE_DIR/loop-watchdog.log"
PIDFILE="$STATE_DIR/loop.pid"
OUT="$STATE_DIR/loop.out"

# Пауза лейна
[ -f "$STATE_DIR/loop.paused" ] && exit 0
# Совместимость: старый общий флаг паузы (до лейнов) тоже уважаем для auto
[ "$LANE" = "auto" ] && [ -f "artifacts/loop.paused" ] && exit 0

# Авто-лейн: если браузер лейна не поднят — поднять (само-лечение, правило 57)
if [ "$LANE" = "auto" ]; then
  if ! curl -s --max-time 4 "http://127.0.0.1:9224/json/version" >/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog(auto): browser 9224 down — launching" >> "$LOG"
    CHROME_BIN="${CHROME_EXE:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
    "$CHROME_BIN" --user-data-dir="$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/browser-data-auto" \
      --remote-debugging-address=127.0.0.1 --remote-debugging-port=9224 \
      --no-first-run --no-default-browser-check \
      "https://app.grayswan.ai/arena/challenge/lucky-break-payday" >/dev/null 2>&1 &
    sleep 10
  fi
fi

# tab-id НЕ хардкодить: pick_target смотрит на HACKATHON_CDP_URL (экспортирован выше).
# ВАЖНО: для auto-лейна ИГНОРИРУЕМ унаследованный CHAT_TARGET (он от main-браузера — target-id'ы у браузеров разные!)
if [ "$LANE" = "auto" ]; then
  TARGET="$(python3 harness/pick_target.py 2>/dev/null)"
else
  TARGET="${CHAT_TARGET:-$(python3 harness/pick_target.py 2>/dev/null)}"
fi
[ -z "${TARGET:-}" ] && { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog($LANE): no LBP tab at $HACKATHON_CDP_URL, skip (браузер лейна не запущен?)" >> "$LOG"; exit 0; }
MAX_AGE="${LOOP_MAX_AGE:-600}"   # heartbeat older than 10 min = considered stuck/dead
MAX_HOURS="${LOOP_MAX_HOURS:-12}"

now=$(date +%s)
alive=0
if [ -f "$PIDFILE" ]; then
  pid=$(cat "$PIDFILE" 2>/dev/null | tr -d '[:space:]')
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then alive=1; fi
fi
# fallback: look for the driver process of THIS lane (по env-маркеру LOOP_STATE_DIR в командной строке)
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

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog($LANE): alive=$alive heartbeat_age=${age}s] -> restarting driver" >> "$LOG"
# kill a stuck driver before starting a fresh one
if [ "$alive" = "1" ]; then
  pkill -f "harness/loop.py" 2>/dev/null || true
  sleep 2
fi
LOOP_STATE_DIR="$STATE_DIR" nohup python3 harness/loop.py --target "$TARGET" --max-hours "$MAX_HOURS" \
  >> "$OUT" 2>&1 &
echo $! > "$PIDFILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog($LANE): started pid $(cat "$PIDFILE") target=$TARGET cdp=$HACKATHON_CDP_URL" >> "$LOG"
