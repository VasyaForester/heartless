(() => {
  const t = document.body.innerText;
  const m = (t.match(/Attacking:\s*\n?\s*([^\n]+)/) || [])[1] || null;
  const jb = document.querySelector('#submitJailbreakButton');
  const banner = (t.match(/BREAK (REJECTED|ACCEPTED)/) || [])[0] || 'none';
  const pcts = (t.match(/(Harmful Content|AI Origination|Realism|Denial of Service|Operational Security)\n\d+%/g) || []);
  const msgHead = (t.match(/Today \d+:\d+[AP]M\n([^\n]{0,80})/) || [])[1] || null;
  return {url: location.href.slice(-70), model: m, banner, judgeDisabled: jb ? jb.disabled : null, pcts: pcts.slice(0, 6), msgHead};
})()
