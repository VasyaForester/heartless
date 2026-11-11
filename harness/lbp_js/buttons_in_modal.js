(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  const out = [];
  for (const d of dlgs) {
    const btns = [...d.querySelectorAll('button,[role="button"],a')].filter(vis)
      .map(e => ({ text: norm(e.innerText).slice(0, 40), aria: e.getAttribute('aria-label'),
                   href: e.href ? e.href.slice(-30) : null }))
      .filter(b => b.text || b.aria);
    if (btns.length) out.push({ dlgLen: (d.innerText || '').length, btns: btns.slice(0, 25) });
  }
  return JSON.stringify({ n: out.length, out: out.slice(0, 3) });
})()
