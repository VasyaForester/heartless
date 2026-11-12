(() => {
  const b = [...document.querySelectorAll('button,a[role="button"]')].find(x => /^NEW/i.test((x.innerText||'').trim()));
  if (!b) return 'no btn';
  b.click();
  return 'clicked:' + (b.innerText||'').trim().slice(0, 30);
})()
