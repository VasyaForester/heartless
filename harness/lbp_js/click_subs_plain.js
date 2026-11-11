(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const b = [...document.querySelectorAll('button,[role="button"],a')].filter(vis)
    .find(e => /^SUBMISSIONS\b/i.test(norm(e.innerText)));
  if (!b) return 'nf';
  b.click();
  return 'plain click';
})()
