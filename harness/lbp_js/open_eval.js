(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const log = [];
  const findModal = () => [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis)
    .find(d => /SUBMITTED/.test(norm(d.innerText)) && /CHATS/.test(norm(d.innerText)));
  let modal = findModal();
  if (!modal) {
    const b = [...document.querySelectorAll('button,[role="button"],a')].filter(vis)
      .find(e => /^SUBMISSIONS\b/i.test(norm(e.innerText)));
    if (!b) return JSON.stringify({ log: ['no submissions button'] });
    b.click(); log.push('opened submissions');
    await sleep(2200);
    modal = findModal();
  }
  const tab = [...document.querySelectorAll('[role="tab"],button,[role="button"]')].filter(vis)
    .find(e => /^SUBMITTED\b/i.test(norm(e.innerText)));
  if (tab && tab.getAttribute('aria-selected') !== 'true') { tab.click(); log.push('submitted tab'); await sleep(1600); }
  let evalBtn = [...document.querySelectorAll('button,[role="button"]')].filter(vis)
    .find(e => /SEE EVALUATION/i.test(norm(e.innerText)));
  if (!evalBtn) {
    const rows = modal ? [...modal.querySelectorAll('a[href*="submissionId="]')].filter(vis) : [];
    const row = rows[0] || [...document.querySelectorAll('a[href*="submissionId="]')].filter(vis)[0];
    if (row) { row.click(); log.push('opened detail ' + String(row.href).slice(-12)); await sleep(2400); }
    evalBtn = [...document.querySelectorAll('button,[role="button"]')].filter(vis)
      .find(e => /SEE EVALUATION/i.test(norm(e.innerText)));
  }
  if (evalBtn) { evalBtn.click(); log.push('clicked SEE EVALUATION'); await sleep(2400); }
  else log.push('NO eval button');
  return JSON.stringify({ log });
})()
