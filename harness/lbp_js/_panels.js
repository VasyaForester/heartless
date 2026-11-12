(() => {
  const txt = e => String(e.innerText || e.textContent || '').trim();
  const cands = [...document.querySelectorAll('[role="dialog"], [class*="modal" i], [class*="Modal"], [class*="drawer" i], [class*="sheet" i], [class*="panel" i]')]
    .filter(e => e.getClientRects().length && txt(e).length > 200);
  cands.sort((a,b) => txt(b).length - txt(a).length);
  const best = cands.slice(0,3).map(e => txt(e).slice(0, 3000));
  return JSON.stringify({n: cands.length, texts: best});
})()