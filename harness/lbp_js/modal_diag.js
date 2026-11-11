(() => {
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"], [class*="dialog" i]')];
  const info = dlgs.slice(0, 12).map(d => ({
    tag: d.tagName.toLowerCase(),
    role: d.getAttribute('role'),
    state: d.getAttribute('data-state'),
    vis: d.getBoundingClientRect().width > 0,
    len: (d.innerText || '').length,
    head: (d.innerText || '').replace(/\s+/g, ' ').slice(0, 70)
  }));
  const body = document.body.innerText || '';
  return JSON.stringify({
    n: info.length, dlgs: info,
    bodyHasSubmitted: /SUBMITTED/.test(body), bodyHasChats: /CHATS/.test(body),
    bodyTail: body.slice(-400).replace(/\n+/g, ' | ')
  });
})()
