(() => {
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const body = document.body ? document.body.innerText : '';
  const solved = /SCENARIO SOLVED/i.test(body);
  const rejected = /Break (Rejected|Unsuccessful|Not Successful)|Submission (Rejected|Failed)/i.test(body);
  const i = body.indexOf('SCENARIO SOLVED');
  const around = i >= 0 ? body.slice(i, i + 600).replace(/\n{2,}/g, '\n') : '';
  const pcts = [...body.matchAll(/([^%\n]{4,90}?)\s*\n\s*(\d{1,3})%/g)].slice(0, 12)
    .map(m => ({ label: norm(m[1]).slice(0, 90), pct: +m[2] }));
  return JSON.stringify({ solved, rejected, around, pcts });
})()
