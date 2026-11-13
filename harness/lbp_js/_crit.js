(() => {
  const btn = [...document.querySelectorAll('button,a')].find(x => (x.innerText||'').toUpperCase().includes('SEE SUCCESS CRITERIA'));
  if (btn) { btn.click(); return 'clicked'; }
  return 'no-button';
})()
