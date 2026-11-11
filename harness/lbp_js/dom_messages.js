(() => {
  const out = [];
  for (const key of ['deliveries never arrived', 'give_refund', 'settle the case']) {
    const els = [...document.querySelectorAll('div,p,section,article,li')]
      .filter(e => (e.innerText || '').includes(key) && e.getClientRects().length);
    if (!els.length) { out.push({ key, found: false }); continue; }
    let cur = els[els.length - 1];
    const chain = [];
    for (let i = 0; i < 8 && cur; i++) {
      chain.push({ tag: cur.tagName.toLowerCase(), testid: cur.getAttribute('data-testid'),
                   role: cur.getAttribute('data-role') || cur.getAttribute('role'),
                   cls: String(cur.className || '').slice(0, 80) });
      cur = cur.parentElement;
    }
    out.push({ key, found: true, chain });
  }
  return JSON.stringify({ out });
})()
