#!/usr/bin/env python3
"""Dump a PPTX: slides -> shapes -> text frames/runs (for template mapping).

Usage: python3 tools/pptx_dump.py <file.pptx> [--shapes-only]
"""
from __future__ import annotations
import sys
from pptx import Presentation


def main():
    fp = sys.argv[1]
    prs = Presentation(fp)
    print(f"slides: {len(prs.slides)}  size: {prs.slide_width}x{prs.slide_height}")
    for si, slide in enumerate(prs.slides):
        print(f"\n===== SLIDE {si + 1} =====")
        for shi, shape in enumerate(slide.shapes):
            kind = shape.shape_type
            name = shape.name
            pos = f"L{shape.left} T{shape.top} W{shape.width} H{shape.height}" if shape.left is not None else "?"
            info = f"[{shi}] {name} ({kind}) {pos}"
            if shape.has_text_frame:
                tf = shape.text_frame
                texts = []
                for pi, para in enumerate(tf.paragraphs):
                    runs = "~".join(r.text for r in para.runs)
                    texts.append(f"    p{pi}: {runs!r}")
                print(info)
                print("\n".join(texts) if texts else "    (empty tf)")
            else:
                print(info)


if __name__ == "__main__":
    main()
