#!/usr/bin/env python3
"""Capture SEE EVALUATION panels for the four scenario-2 accepts (submission pages).

Opens each submission URL in the pinned tab, clicks SEE EVALUATION (if needed),
saves the eval text around SCORES/verdict keys to artifacts/pg-eval-<name>.txt.
"""
import os
import subprocess
import sys
import time

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = "5ED8D39575C312086CD9EC03254BF9BA"
SUBS = {
    "black-squid": "6af3632d002e1f874444d0b5",
    "bronze-salmon": "6af3638f5c7df088a4227ded",
    "sand-elephant": "6af36261db5ae3d5cfaf07e4",
    "water-ostrich": "6af3622a1dc089e09bfee90d",
}
JS = (
    "(async()=>{ await new Promise(r=>setTimeout(r,2500)); "
    "const b=[...document.querySelectorAll('button')].find(x=>/evaluation/i.test(x.textContent||'')); "
    "if(b && !document.body.innerText.includes('Mr. Swan')){ b.click(); await new Promise(r=>setTimeout(r,2200)); } "
    "return document.body.innerText; })()"
)


def main():
    for name, sid in SUBS.items():
        url = f"https://app.grayswan.ai/arena/challenge/proving-ground?submissionId={sid}"
        subprocess.run(
            [sys.executable, "harness/hackathon.py", "arena", "open", "--target", TARGET, "--url", url],
            cwd=WS, capture_output=True, text=True,
        )
        time.sleep(2)
        r = subprocess.run(["node", "harness/eval-page.mjs", "--target", TARGET, "--js", JS],
                           cwd=WS, capture_output=True, text=True)
        out = (r.stdout or r.stderr or "").strip()
        p = os.path.join(WS, "artifacts", f"pg-eval-{name}.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"== {name}: saved {p} ({len(out)} chars)")
        print(out[:500].replace("\n", " | "))
        print()


if __name__ == "__main__":
    main()
