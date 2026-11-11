(() => {
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  const btn = [...document.querySelectorAll('button,a,div,span,p,summary')]
    .find(e => /SEE SUCCESS CRITERIA/i.test(txt(e)) && txt(e).length < 60 && e.getClientRects().length);
  const res = { clicked: !!btn, url: location.href };
  if (btn) {
    const tag = btn.tagName;
    res.tag = tag;
    btn.scrollIntoView({ block: 'center' });
    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    btn.click();
    const clickable = btn.closest('button,a,[role=button]');
    if (clickable && clickable !== btn) clickable.click();
  }
  return JSON.stringify(res);
})()
