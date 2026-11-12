#!/usr/bin/env bash
# lane_auto.sh — изолированный лейн автопилота (правило 57): собственный Chrome (CDP 9224,
# профиль browser-data-auto) + один тик watchdog. Живая сессия (CDP 9223) не затрагивается.
# Запуск: bash tools/lane_auto.sh
set -u
cd "$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2/workspace" || exit 1
PROF="$HOME/AppData/Local/hermes/profiles/gray-swan-hackathon-v2"
PORT="${LANE_PORT:-9224}"
URL="https://app.grayswan.ai/arena/challenge/lucky-break-payday"
CHROME="${CHROME_EXE:-/c/Program Files/Google/Chrome/Application/chrome.exe}"

if ! curl -s --max-time 5 "http://127.0.0.1:$PORT/json/version" >/dev/null; then
  echo "lane_auto: launching browser on $PORT (profile browser-data-auto)"
  "$CHROME" --user-data-dir="$PROF/browser-data-auto" \
    --remote-debugging-address=127.0.0.1 --remote-debugging-port="$PORT" \
    --no-first-run --no-default-browser-check "$URL" >/dev/null 2>&1 &
  sleep 8
fi
export HACKATHON_CDP_URL="http://127.0.0.1:$PORT"
echo "lane_auto: cdp=$HACKATHON_CDP_URL"
TARGET="$(python3 harness/pick_target.py 2>/dev/null)"
echo "lane_auto: target=${TARGET:-<none>}"
if [ -z "${TARGET:-}" ]; then
  echo "lane_auto: arena tab не найден на $PORT — открой арену/залогинься в профиле browser-data-auto"
  exit 1
fi
LOOP_LANE=auto CHAT_TARGET="$TARGET" bash tools/loop_watchdog.sh
echo "lane_auto: watchdog tick done"
