(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const b = [...document.querySelectorAll('button,[role="button"],a')].filter(vis)
    .find(e => /^SUBMISSIONS\b/i.test(norm(e.innerText)));
  let brief = null;
  if (b) {
    const r = b.getBoundingClientRect();
    brief = { tag: b.tagName, disabled: !!b.disabled,
              ariaDisabled: b.getAttribute('aria-disabled'),
              rect: { w: r.width, h: r.height, x: r.x, y: r.y },
              cls: String(b.className || '').slice(0, 140) };
  }
  const bpe = getComputedStyle(document.body).pointerEvents;
  const locked = document.body.getAttribute('data-scroll-locked');
  return JSON.stringify({ btn: brief, bodyPointerEvents: bpe, bodyScrollLocked: locked });
})()
