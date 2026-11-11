(() => {
  const names = ['Get Free Money','Double the Refund','Gift Card','Negative','Identity Theft','Lots of Money'];
  const out = [];
  for (const el of document.querySelectorAll('a,button,[role=tab],[role=button]')) {
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t || t.length > 60) continue;
    if (names.some(n => t.includes(n))) {
      out.push({ tag: el.tagName, href: el.getAttribute('href'), text: t.slice(0, 60), cls: String(el.className).slice(0,40) });
    }
  }
  return JSON.stringify(out.slice(0, 20));
})()