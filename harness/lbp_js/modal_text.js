(() => {
  const dlgs = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')];
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const texts = dlgs.filter(vis).map(d => (d.innerText || '').slice(0, 2500));
  const body = document.body.innerText || '';
  const i = body.indexOf('SUBMISSION');
  return JSON.stringify({ n_dialogs: texts.length, dialogs: texts,
    bodyAround: i >= 0 ? body.slice(i, i + 2400) : body.slice(-1800) });
})()
