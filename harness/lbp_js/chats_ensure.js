(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const body = document.body.innerText || '';
  // Body-level detection: the closed board never shows the SUBMITTED/CHATS modal chrome.
  const modalOpen = /CHATS/.test(body) && /SUBMITTED/.test(body) && /(SHOWING 1-|Most recent)/.test(body);
  if (!modalOpen) {
    const b = [...document.querySelectorAll('button,[role="button"],a')].filter(vis)
      .find(e => /^SUBMISSIONS\b/i.test(norm(e.innerText)));
    if (!b) return 'no submissions button';
    try { const pev = (ty, C) => b.dispatchEvent(new C(ty, { bubbles: true, cancelable: true, pointerType: 'mouse', button: 0, view: window }));
      pev('pointerdown', PointerEvent); pev('mousedown', MouseEvent); pev('pointerup', PointerEvent); pev('mouseup', MouseEvent); } catch {}
    b.click();
    return 'opened submissions';
  }
  const tabs = [...document.querySelectorAll('[role="tab"],button,[role="button"]')].filter(vis)
    .filter(e => /^CHATS\b/i.test(norm(e.innerText)));
  const t = tabs[tabs.length - 1];
  if (t && t.getAttribute('aria-selected') !== 'true') {
    try { const pev = (ty, C) => t.dispatchEvent(new C(ty, { bubbles: true, cancelable: true, pointerType: 'mouse', button: 0, view: window }));
      pev('pointerdown', PointerEvent); pev('mousedown', MouseEvent); pev('pointerup', PointerEvent); pev('mouseup', MouseEvent); } catch {}
    t.click(); return 'clicked chats tab';
  }
  return 'already on chats';
})()
