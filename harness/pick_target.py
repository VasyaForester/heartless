#!/usr/bin/env python3
"""pick_target.py — печатает tabId grayswan-вкладки активной доски (профиль boards.py).

Правило (Grok review 2026-11-15, «транспорт/устойчивость»): при НЕОДНОЗНАЧНОСТИ
(две и более подходящих вкладок) скрипт НЕ угадывает, а падает — попытка должна
ошибиться, а не уехать в чужой чат.  Коды выхода: 0 — одна вкладка (её id в stdout),
1 — подходящих нет, 2 — неоднозначно (список в stderr).

Выбор вынесен в чистую функцию `choose(tabs, needle)`, поэтому он проверяется тестом
без браузера (`harness/tests/test_pick_target.py`).
"""
import json, os, sys, urllib.request
from urllib.parse import urlsplit

# Порт CDP берём из HACKATHON_CDP_URL (лейны: main=9223, auto=9224), по умолчанию 9223.
PORT = 9223
try:
    _u = urlsplit(os.environ.get("HACKATHON_CDP_URL", ""))
    if _u.port:
        PORT = _u.port
except Exception:
    pass


def board_needle() -> str:
    """The tab match string: the board profile's `match` ($HERMES_BOARD aware)."""
    if "--pg" in sys.argv:
        return "proving-ground"
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from boards import load_board  # noqa: E402
        return str(load_board().get("match") or "lucky-break-payday")
    except Exception:
        return "lucky-break-payday"


def choose(tabs: list, needle: str) -> tuple:
    """(tab_id | None, reason, exit_code) — the ONLY place the target is decided.

    Exactly one match wins; zero is "none"; two or more is "ambiguous" and the caller
    must treat it as an attempt error.  No freshness guessing: the order of tabs in the
    CDP listing is not a clock, and picking "the last one" is exactly how a probe lands
    in the wrong chat.
    """
    cands = [t for t in tabs
             if t.get("type") == "page"
             and "grayswan.ai" in (t.get("url") or "")
             and needle in (t.get("url") or "")]
    if not cands:
        return None, f"no tab matching {needle!r}", 1
    if len(cands) > 1:
        urls = ", ".join(sorted({(t.get("url") or "")[:70] for t in cands}))
        return None, f"ambiguous: {len(cands)} tabs match {needle!r} ({urls})", 2
    return cands[0].get("id"), "unique match", 0


def main() -> int:
    needle = board_needle()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5) as r:
            tabs = json.load(r)
    except Exception as exc:  # noqa: BLE001 — CDP down: no target, same as none
        print(f"pick_target: CDP on {PORT} unreachable ({type(exc).__name__})",
              file=sys.stderr)
        return 1
    tab_id, reason, code = choose(tabs, needle)
    if code != 0:
        print(f"pick_target: {reason}", file=sys.stderr)
        return code
    print(tab_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
