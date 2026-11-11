(() => {
  let n = 0;
  const els = [...document.querySelectorAll('div')];
  for (const el of els) {
    if (el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 200) {
      el.scrollTop = el.scrollHeight;
      n++;
    }
  }
  return JSON.stringify({ scrolled: n, links: document.querySelectorAll('a[href*="chatId="]').length });
})()