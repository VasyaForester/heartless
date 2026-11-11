(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  for (const d of dlgs) {
    const rows = [...d.querySelectorAll('*')].filter(e => /Get Free Money/.test(norm(e.innerText)) && norm(e.innerText).length < 2000);
    const row = rows[rows.length - 1];
    if (!row) continue;
    const btn = [...row.querySelectorAll('button,[role="button"],a')].filter(vis)
      .concat([...d.querySelectorAll('button,[role="button"],a')].filter(vis).filter(e => /SEE EVALUATION/i.test(norm(e.innerText))))
      .find(e => /SEE EVALUATION|Evaluation/i.test(norm(e.innerText)));
    if (btn) { btn.click(); return 'clicked: ' + norm(btn.innerText).slice(0, 40); }
  }
  return 'nf';
})()
