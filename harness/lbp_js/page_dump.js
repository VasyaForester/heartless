(() => {
  const t = document.body.innerText || '';
  const buttons = [...document.querySelectorAll('button,[role=button],[role=tab],select')].slice(0, 40).map(b => ({
    tag: b.tagName,
    aria: b.getAttribute('aria-label') || '',
    text: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40)
  })).filter(b => b.text || b.aria);
  return JSON.stringify({ head: t.slice(0, 600), buttons: buttons.slice(0, 25) });
})()