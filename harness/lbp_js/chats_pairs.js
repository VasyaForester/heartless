(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  const rows = [];
  for (const d of dlgs) {
    for (const a of d.querySelectorAll('a[href*="chatId="]')) {
      const t = norm(a.innerText);
      if (t.length > 20) rows.push({ href: a.href, text: t.slice(0, 150) });
    }
  }
  const seen = new Set(); const uniq = [];
  for (const r of rows) { const k = r.href; if (!seen.has(k)) { seen.add(k); uniq.push(r); } }
  return JSON.stringify({ n: uniq.length, rows: uniq });
})()
