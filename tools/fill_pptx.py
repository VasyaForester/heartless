#!/usr/bin/env python3
"""Fill the participant PPTX template with session statistics.

Usage:
  python3 tools/fill_pptx.py <template.pptx> <out.pptx> <diagram.png>

Fills technical fields (breaks, per-area progress, stack, ideas, diagram);
leaves identity placeholders (name/nickname/profile link/rank/area-direction)
for the participant. Never modifies the source file.
"""
from __future__ import annotations
import sys
from pptx import Presentation
from pptx.util import Emu


def set_text_preserve(shape, new):
    """Put text into the first run, blank the others (keeps run 0 formatting)."""
    tf = shape.text_frame
    runs = []
    for p in tf.paragraphs:
        runs.extend(list(p.runs))
    if not runs:
        tf.text = new
        return
    runs[0].text = new
    for r in runs[1:]:
        r.text = ""


def find(slide, name_part):
    for sh in slide.shapes:
        if name_part.lower() in sh.name.lower():
            return sh
    raise KeyError(name_part)


def main():
    tpl, out, diagram = sys.argv[1], sys.argv[2], sys.argv[3]
    prs = Presentation(tpl)
    s1, s2 = prs.slides[0], prs.slides[1]

    set_text_preserve(find(s1, "Total Breaks"), "12")
    set_text_preserve(find(s1, "Chat"), "6  / 450")
    set_text_preserve(find(s1, "Image"), "6  / 328")
    set_text_preserve(find(s1, "Agent"), "0  / 490")
    set_text_preserve(find(s1, "Indirect"), "0  / 444")
    # identity fields (from the participant's live profile)
    set_text_preserve(find(s1, "Никнейм профиля"), "f0r3573r")
    set_text_preserve(find(s1, "Ссылка на публичный профиль"),
                      "https://app.grayswan.ai/arena/user/6aec920f3fbcb643a68af64d")
    set_text_preserve(find(s1, "Proving Ground Global Ranking"), "#324")
    set_text_preserve(find(s1, "Стек решения"),
                      "Hermes Agent (deepseek-chat via OpenRouter) + CDP-харнесс + FTS5-RAG (1,6 млн атак) + скиллы")

    # diagram into the harness-schema placeholder
    ph = find(s1, "архитектуру харнеса")
    s1.shapes.add_picture(diagram, ph.left, ph.top, ph.width, ph.height)

    ideas = [
        ("Ред-тиминг корпоративных LLM-агентов",
         "Харнесс (сценарии + авто-оценка + самопочинка) как воспроизводимый конвейер проверки внутренних "
         "ассистентов и tool/браузерных агентов на устойчивость к прямым и косвенным промпт-инъекциям: "
         "регламентные сценарии, вердикты с доказательствами, регрессия после смены модели или промпта."),
        ("База знаний атак для защиты (blue team)",
         "Корпус 1,6 млн реальных попыток (113 тыс. успешных) + FTS5-поиск и таксономия фреймов обхода — "
         "для разработки и тестирования фильтров и гардрейлов, обогащения детект-правил и тренировки "
         "аналитиков SOC на живых техниках."),
        ("Аудит агентных интеграций через анализ траекторий",
         "Анализ траекторий агента (подходы MUZZLE/GOAT): какие внешние источники реально влияют на действия; "
         "выбор точек инъекции по поведению, а не по шаблону — для security-review браузерных и tool-calling "
         "агентов на этапе внедрения. Пилот проверен на реальных трейсах."),
    ]
    title_shapes = ["Название идеи 1", "Название идеи 2", "Название идеи 3"]
    desc_shapes = ["Описание идеи 1", "Описание идеи 2", "Описание идеи 3"]
    for t_name, d_name, (t, dsc) in zip(title_shapes, desc_shapes, ideas):
        set_text_preserve(find(s2, t_name), t)
        set_text_preserve(find(s2, d_name), dsc)

    prs.save(out)
    print("saved:", out)

    # verify
    prs2 = Presentation(out)
    for label, sh in [("TotalBreaks", find(prs2.slides[0], "Total Breaks")),
                      ("Chat", find(prs2.slides[0], "Chat")),
                      ("Image", find(prs2.slides[0], "Image")),
                      ("Agent", find(prs2.slides[0], "Agent")),
                      ("Indirect", find(prs2.slides[0], "Indirect")),
                      ("Стек", find(prs2.slides[0], "Стек решения")),
                      ("Idea1", find(prs2.slides[1], "Название идеи 1"))]:
        print(f"  {label}: {sh.text_frame.text[:80]}")
    pics = [sh for sh in prs2.slides[0].shapes if sh.shape_type == 13]
    print("  pictures on slide1:", len(pics))


if __name__ == "__main__":
    main()
