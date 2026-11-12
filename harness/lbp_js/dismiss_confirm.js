(() => {
  const dlgs = [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(e => e.getClientRects().length);
  if (!dlgs.length) return 'no dialog';
  const d = dlgs[dlgs.length - 1];
  const btns = [...d.querySelectorAll('button')].filter(b => b.getClientRects().length);
  const b = btns.find(x => /switch|confirm|yes|continue|ok|proceed/i.test(x.innerText || ''));
  if (b) { b.click(); return 'clicked:' + (b.innerText || '').trim().slice(0, 24); }
  return 'dialog:' + (d.innerText || '').replace(/\s+/g, ' ').slice(0, 80);
})()