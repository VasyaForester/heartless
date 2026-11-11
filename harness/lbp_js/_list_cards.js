
(() => {
  const btns = [...document.querySelectorAll('button')].filter(b => (b.innerText||'').includes('Broken at least once'));
  return JSON.stringify(btns.map(b => (b.innerText||'').replace(/\s+/g,' ').slice(0,110)));
})()
