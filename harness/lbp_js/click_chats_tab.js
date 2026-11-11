(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const cands = [...document.querySelectorAll('[role="tab"],button,[role="button"]')].filter(vis)
    .filter(e => /^CHATS\b/i.test(norm(e.innerText)));
  if (!cands.length) return 'nf chats tab';
  const t = cands[cands.length - 1];
  const ev = (ty, C) => t.dispatchEvent(new C(ty, { bubbles: true, cancelable: true, pointerType: 'mouse', button: 0 }));
  ev('pointerdown', PointerEvent); ev('mousedown', MouseEvent); ev('pointerup', PointerEvent); ev('mouseup', MouseEvent);
  t.click();
  return 'clicked CHATS tab (' + norm(t.innerText).slice(0, 20) + ')';
})()
