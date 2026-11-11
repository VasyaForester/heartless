(() => {
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  const btns = [...document.querySelectorAll('button,a,[role=button]')]
    .filter(e => /SEE SUCCESS CRITERIA/i.test(txt(e)) && e.getClientRects().length);
  const b = btns[0];
  if (!b) return JSON.stringify({ clicked: false, n: btns.length });
  const r = b.getBoundingClientRect();
  const x = r.x + r.width / 2, y = r.y + r.height / 2;
  const opts = { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window };
  b.dispatchEvent(new PointerEvent('pointerdown', opts));
  b.dispatchEvent(new MouseEvent('mousedown', opts));
  b.dispatchEvent(new PointerEvent('pointerup', opts));
  b.dispatchEvent(new MouseEvent('mouseup', opts));
  b.click();
  return JSON.stringify({ clicked: true, at: [Math.round(x), Math.round(y)] });
})()
