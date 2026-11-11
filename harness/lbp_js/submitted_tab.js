(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  for (const d of dlgs) {
    const t = [...d.querySelectorAll('[role="tab"],button,[role="button"]')].filter(vis)
      .find(e => /^SUBMITTED\b/i.test(norm(e.innerText)));
    if (t) { t.click(); return 'submitted tab clicked'; }
  }
  return 'nf';
})()
