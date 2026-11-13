(() => {
  const t = document.body.innerText || '';
  const i = t.toUpperCase().indexOf('EVALUATION');
  return t.slice(Math.max(0, i-100), i+3500);
})()
