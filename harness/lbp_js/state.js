(() => {
  const q = s => [...document.querySelectorAll(s)];
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const body = document.body ? document.body.innerText : '';
  let panelTitle = '';
  for (const e of q('h1,h2,h3,h4').filter(vis)) {
    const t = norm(e.innerText);
    if (/Retail Bot|Double the Refund|Gift Card|Exploit the System|Identity Theft/i.test(t)) { panelTitle = t; break; }
  }
  let attacking = '';
  const mAtt = body.match(/Attacking:\s*\n\s*([^\n]{2,60})/);
  if (mAtt) attacking = norm(mAtt[1]);
  if (!attacking) {
    let best = '';
    for (const e of q('button,[role="button"],div,span').filter(vis)) {
      const t = norm(e.innerText);
      if (/^Attacking:/.test(t)) {
        const cut = t.replace(/^Attacking:\s*/i, '').split(/\s+(?:SUBMISSIONS|SUBMIT BREAK|Model|MODEL)\b/)[0];
        if (cut && (!best || cut.length < best.length)) best = cut;
      }
    }
    attacking = best;
  }
  const em = body.match(/Energy\s+(\d+)\s+of\s+(\d+)(?:\s*,?\s*plus\s+(\d+)\s+bonus)?/i);
  const energy = em ? { current: +em[1], max: +em[2], bonus: em[3] ? +em[3] : 0 } : null;
  const sb = q('#submitJailbreakButton').filter(vis)[0];
  const sc = q('#submitChatButton').filter(vis)[0];
  const ta = document.querySelector('#chatTextarea');
  const solved = /SCENARIO SOLVED/i.test(body);
  const pcts = [...body.matchAll(/([^%\n]{4,90}?)\s*\n\s*(\d{1,3})%/g)].slice(0, 10)
    .map(m => ({ label: norm(m[1]).slice(0, 90), pct: +m[2] }));
  return JSON.stringify({
    url: location.href, panelTitle, attacking, energy, solved, pcts,
    submitBreak: sb ? { text: norm(sb.innerText), disabled: !!sb.disabled } : null,
    submitChat: sc ? { disabled: !!sc.disabled } : null,
    textarea: ta ? { present: true, empty: ta.value.length === 0, placeholder: ta.placeholder || '' }
                 : { present: false }
  });
})()
