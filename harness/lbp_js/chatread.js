(() => {
  const q = s => [...document.querySelectorAll(s)];
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  const els = q('[data-testid="assistantMessage"],[data-testid="userMessage"],[data-message-role],[data-role="assistant"],[data-role="user"],.assistant-message,.model-response,.ai-message')
    .filter(e => e.getClientRects().length);
  const top = els.filter(e => !els.some(o => o !== e && o.contains(e)));
  const role = e => {
    const a = [e.getAttribute('data-testid'), e.getAttribute('data-message-role'), e.getAttribute('data-role')].join(' ');
    if (/user/i.test(a)) return 'user';
    if (/assistant|model|ai/i.test(a)) return 'assistant';
    return 'unknown';
  };
  const msgs = top.map(e => ({ role: role(e), text: txt(e).slice(-1500) }));
  return JSON.stringify({
    n: msgs.length, messages: msgs,
    bodyTail: (document.body ? document.body.innerText : '').slice(-2500)
  });
})()
