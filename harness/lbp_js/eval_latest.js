(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis);
  for (const d of dlgs) {
    const b = [...d.querySelectorAll('button,[role="button"],a')].filter(vis)
      .find(e => /SEE EVALUATION|View evaluation|Evaluation/i.test(norm(e.innerText)));
    if (b) { b.click(); return 'clicked eval: ' + norm(b.innerText).slice(0, 40); }
  }
  const any = [...document.querySelectorAll('button,[role="button"],a')].filter(vis)
    .filter(e => /SEE EVALUATION|View evaluation/i.test(norm(e.innerText)));
  if (any.length) { any[0].click(); return 'clicked eval (global): ' + norm(any[0].innerText).slice(0, 40); }
  const row = [...document.querySelectorAll('a[href*="submissionId="]')].filter(vis)[0];
  if (row) { row.click(); return 'clicked row: ' + (row.href.split('submissionId=')[1] || '').slice(0, 12); }
  return 'no eval button';
})()
