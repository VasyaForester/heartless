(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  const grab = () => [...document.querySelectorAll('a[href*="submissionId="]')].filter(vis).map(a => a.href);
  let links = grab();
  if (!links.length) {
    const tabs = [...document.querySelectorAll('[role="tab"],button,[role="button"]')].filter(vis)
      .filter(e => /^SUBMITTED\b/i.test(norm(e.innerText)));
    const t = tabs[tabs.length - 1];
    if (t) { t.click(); await sleep(2000); links = grab(); }
  }
  return JSON.stringify({ count: links.length, links });
})()
