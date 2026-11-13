(() => {
  const t = document.body.innerText || '';
  const i = t.toUpperCase().indexOf('SUCCESS CRITERIA');
  return t.slice(Math.max(0, i-200), i+4000);
})()
