(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const btns = [...document.querySelectorAll('button,[role="button"],a')]
    .filter(vis)
    .map(e => ({ text: norm(e.innerText).slice(0, 60), id: e.id || null,
                 testid: e.getAttribute('data-testid'), aria: e.getAttribute('aria-label') }))
    .filter(b => b.text || b.id || b.testid || b.aria);
  return JSON.stringify({ btns: btns.slice(0, 60) });
})()
