(() => {
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  const all = [...document.querySelectorAll('button,a,div,span,p')];
  const btn = all.find(e => /SEE SUCCESS CRITERIA/i.test(txt(e)) && txt(e).length < 60 && e.getClientRects().length);
  if (btn) btn.click();
  return (() => {
    const body = document.body ? document.body.innerText : '';
    const i = body.search(/Scenario criteria|Success Criteria/i);
    return JSON.stringify({ clicked: !!btn, tail: i >= 0 ? body.slice(i, i + 2500) : body.slice(-1500) });
  })();
})()
