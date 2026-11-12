(() => {
  const q = s => [...document.querySelectorAll(s)];
  const ta = document.querySelector('#chatTextarea') || q('textarea').find(e => e.getClientRects().length) || null;
  const els = q('[data-testid="assistantMessage"],[data-testid="userMessage"],[data-message-role],[data-role="assistant"],[data-role="user"],.assistant-message,.model-response,.ai-message')
    .filter(e => e.getClientRects().length);
  const top = els.filter(e => !els.some(o => o !== e && o.contains(e)));
  const attr = e => [e.getAttribute('data-testid'), e.getAttribute('data-message-role'), e.getAttribute('data-role')].join(' ');
  const users = top.filter(e => /user/i.test(attr(e)));
  const lastUser = users.length ? String(users[users.length - 1].innerText || '').trim() : '';
  const sb = document.querySelector('#submitChatButton');
  return JSON.stringify({
    n: top.length,
    ta: ta ? String(ta.value || '') : '',
    lastUserFirst: lastUser.slice(0, 220),
    lastUserTail: lastUser.slice(-220),
    sendBtn: sb ? (sb.disabled ? 'disabled' : 'ready') : 'missing'
  });
})()