import sys, re, html
p = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else None
t = open(p, encoding="utf-8", errors="replace").read()
t = re.sub(r"<script.*?</script>", " ", t, flags=re.S | re.I)
t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
t = re.sub(r"<[^>]+>", " ", t)
t = html.unescape(t)
t = re.sub(r"[ \t]+", " ", t)
t = re.sub(r"\r", "", t)
t = re.sub(r"\n\s*\n+", "\n\n", t)
t = t.strip()
if out:
    open(out, "w", encoding="utf-8").write(t)
    print(f"written {out} ({len(t)} chars)")
else:
    print(t)
