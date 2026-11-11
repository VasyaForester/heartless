(() => {
  const q = s => [...document.querySelectorAll(s)];
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  let els = q('[data-testid="assistantMessage"],[data-testid="userMessage"],[data-message-role],[data-role="assistant"],[data-role="user"]')
    .filter(e => e.getClientRects().length);
  if (!els.length) {
    const main = document.querySelector('main') || document.body;
    return JSON.stringify({ mode: 'main', text: txt(main).slice(-6000) });
  }
  const top = els.filter(e => !els.some(o => o !== e && o.contains(e)));
  const role = e => {
    const a = [e.getAttribute('data-testid'), e.getAttribute('data-message-role'), e.getAttribute('data-role')].join(' ');
    return /user/i.test(a) ? 'user' : 'assistant';
  };
  const msgs = top.map(e => ({ role: role(e), text: txt(e) }));
  return JSON.stringify({ mode: 'messages', n: msgs.length, last: msgs[msgs.length - 1], all: msgs.slice(-4) });
})()
