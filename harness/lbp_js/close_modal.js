(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  for (const d of dlgs) {
    const b = [...d.querySelectorAll('button,[role="button"]')].filter(vis)
      .find(e => /^Close$/i.test(norm(e.innerText)) || /close/i.test(e.getAttribute('aria-label') || ''));
    if (b) { b.click(); return 'closed'; }
  }
  return 'no close btn';
})()
