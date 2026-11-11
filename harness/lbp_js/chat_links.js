(() => {
  const out = [];
  const links = [...document.querySelectorAll('a[href*="chatId="]')];
  for (const a of links) {
    const t = (a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 140);
    out.push({ href: a.getAttribute('href'), t });
  }
  return JSON.stringify(out.slice(0, 60));
})()