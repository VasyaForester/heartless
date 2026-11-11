(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const log = [];
  // 0. If the evaluation is already visible, do not toggle anything.
  if (/SCORES|Mr\. Swan/.test(document.body.innerText || '')) { log.push('eval already visible'); return JSON.stringify({ log }); }
  // 1. If a SEE EVALUATION button is already visible (page or detail view), just click it.
  let eb = [...document.querySelectorAll('button,[role="button"]')].filter(vis)
    .find(e => /SEE EVALUATION/i.test(norm(e.innerText)));
  if (eb) { eb.click(); log.push('clicked see-eval (already open)'); await sleep(2500); return JSON.stringify({ log }); }
  // 2. Open the submissions modal (pointer-cycle click).
  let modal = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis)
    .find(d => /SUBMITTED/.test(norm(d.innerText)) && /CHATS/.test(norm(d.innerText)));
  if (!modal) {
    const b = [...document.querySelectorAll('button,[role="button"],a')].filter(vis)
      .find(e => /^SUBMISSIONS\b/i.test(norm(e.innerText)));
    if (!b) return JSON.stringify({ log: ['no submissions button'] });
    try { const pev = (ty, C) => b.dispatchEvent(new C(ty, { bubbles: true, cancelable: true, pointerType: 'mouse', button: 0, view: window }));
      pev('pointerdown', PointerEvent); pev('mousedown', MouseEvent); pev('pointerup', PointerEvent); pev('mouseup', MouseEvent); } catch {}
    b.click(); log.push('opened submissions'); await sleep(2200);
    modal = [...document.querySelectorAll('[role="dialog"], [data-state="open"]')].filter(vis)
      .find(d => /SUBMITTED/.test(norm(d.innerText)) && /CHATS/.test(norm(d.innerText)));
  }
  const tab = [...document.querySelectorAll('[role="tab"],button,[role="button"]')].filter(vis)
    .find(e => /^SUBMITTED\b/i.test(norm(e.innerText)));
  if (tab && tab.getAttribute('aria-selected') !== 'true') { tab.click(); log.push('submitted tab'); await sleep(1500); }
  // 3. Click ROW #2 (0-based) -> submission page.
  const row = (modal ? [...modal.querySelectorAll('a[href*="submissionId="]')].filter(vis)[2] : null)
    || [...document.querySelectorAll('a[href*="submissionId="]')].filter(vis)[2];
  if (row) { row.click(); log.push('opened submission page row2'); await sleep(2800); }
  else log.push('no submission row at index 2');
  // 4. SEE EVALUATION on the submission page.
  eb = [...document.querySelectorAll('button,[role="button"]')].filter(vis)
    .find(e => /SEE EVALUATION/i.test(norm(e.innerText)));
  if (eb) { eb.click(); log.push('clicked see-eval'); await sleep(2800); }
  else log.push('no see-eval button');
  return JSON.stringify({ log });
})()
