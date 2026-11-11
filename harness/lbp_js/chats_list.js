(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  const rows = [];
  for (const d of dlgs) {
    for (const e of d.querySelectorAll('[class*="row" i], [role="listitem"], article, a[href], [data-chat-id], [class*="card" i]')) {
      const t = norm(e.innerText);
      if (t && t.length > 20) rows.push({ text: t.slice(0, 400), href: e.href || null,
        chatId: e.getAttribute('data-chat-id') || null });
    }
  }
  const uniq = [];
  const seen = new Set();
  for (const r of rows) { const k = r.text.slice(0, 80); if (!seen.has(k)) { seen.add(k); uniq.push(r); } }
  return JSON.stringify({ n: uniq.length, rows: uniq.slice(0, 30) });
})()
