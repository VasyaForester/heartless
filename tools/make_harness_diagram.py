#!/usr/bin/env python3
"""Render the harness architecture diagram (dark theme, RU) for the participant deck.

Usage: python3 tools/make_harness_diagram.py [out.png]
"""
from __future__ import annotations
import math
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 2600, 1900
BG = (16, 17, 21)
PANEL = (27, 30, 37)
BORDER = (58, 62, 74)
ACCENT = (255, 212, 0)
TXT = (238, 238, 240)
SUB = (166, 171, 182)
GREEN = (130, 220, 130)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def F(sz, bold=False):
    try:
        p = "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
        return ImageFont.truetype(p, sz)
    except Exception:
        p = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
        return ImageFont.truetype(p, sz)


f_title = F(78, True)
f_sub = F(42)
f_box = F(50, True)
f_line = F(37)
f_small = F(34)
f_chip = F(40, True)


def box(x, y, w, h, title, lines, tcol=ACCENT, lsz=None):
    d.rounded_rectangle((x, y, x + w, y + h), radius=22, fill=PANEL, outline=BORDER, width=3)
    d.text((x + 34, y + 26), title, font=f_box, fill=tcol)
    yy = y + 26 + 62
    for ln in lines:
        d.text((x + 34, yy), ln, font=lsz or f_line, fill=TXT)
        yy += (lsz or f_line).size + 16


def arrow(x1, y1, x2, y2, col=ACCENT, w=7):
    d.line((x1, y1, x2, y2), fill=col, width=w)
    ang = math.atan2(y2 - y1, x2 - x1)
    L = 30
    xa, ya = x2 - L * math.cos(ang), y2 - L * math.sin(ang)
    d.polygon([(x2, y2),
               (xa - L * 0.5 * math.sin(ang), ya + L * 0.5 * math.cos(ang)),
               (xa + L * 0.5 * math.sin(ang), ya - L * 0.5 * math.cos(ang))], fill=col)


# header
d.text((80, 52), "АРХИТЕКТУРА ХАРНЕСА — GRAY SWAN", font=f_title, fill=ACCENT)
d.text((82, 152), "Модель • инструменты • память • скиллы • цикл работы", font=f_sub, fill=SUB)

# chips
chips = ["10/53 breaks", "2/4 сценария", "38 попыток в журнале"]
cx = 80
for c in chips:
    tw = d.textlength(c, font=f_chip)
    d.rounded_rectangle((cx, 224, cx + tw + 56, 298), radius=34, outline=ACCENT, width=3)
    d.text((cx + 28, 238), c, font=f_chip, fill=ACCENT)
    cx += tw + 96

# left: Hermes agent
box(80, 380, 820, 640, "HERMES AGENT", [
    "LLM: deepseek-chat",
    "(OpenRouter)",
    "",
    "Скиллы: 4",
    "процедурная память:",
    "prompt-injection-ctf-solver,",
    "gray-swan-*",
])

# right column: three boxes
box(1020, 380, 1500, 480, "CDP-ХАРНЕСС (браузер)", [
    "select_model → fill → upload → send → judge",
    "farm.py — батч по моделям, чекпойнт и резюм",
    "arena_heal.py — авто-починки (scope, вердикты)",
    "classify_response.py — класс ответа + pre-judge",
])

box(1020, 920, 1500, 380, "ПАМЯТЬ И ЗНАНИЯ", [
    "attempts.jsonl — 38 событий, 10 подтверждённых пар",
    "RAG FTS5 (2,1 ГБ): 1 607 971 атака",
    "113 820 успешных — поиск техник и формулировок",
])

box(1020, 1360, 1500, 380, "GRAY SWAN ARENA", [
    "Proving Ground: Chat • Image • Agent • Indirect",
    "Вердикт судьи → запись результата и доказательств",
    "10/53 breaks • 2/4 сценария решено",
], tcol=GREEN)

# arrows Hermes -> boxes
arrow(900, 520, 1020, 520)
arrow(900, 700, 1020, 1080)
arrow(900, 880, 1020, 1520)

# return loop: arena -> hermes (bottom)
d.line((1020 + 750, 1760, 490, 1760), fill=SUB, width=5)
d.line((490, 1760, 490, 1020), fill=SUB, width=5)
arrow(490, 1080, 490, 1020, col=SUB, w=5)
d.text((560, 1712), "результат → решение о следующем эксперименте", font=f_small, fill=SUB)

# bottom cycle strip
d.rounded_rectangle((80, 1802, 2520, 1890), radius=18, fill=(24, 26, 32), outline=BORDER, width=2)
d.text((110, 1830), "ЦИКЛ: разведка → фрейминг (RAG) → отправка → классификация → судья → запись → решение",
       font=f_small, fill=TXT)

out = sys.argv[1] if len(sys.argv) > 1 else "deliverables/harness-architecture.png"
img.save(out)
print("saved:", out, img.size)
