(() => {
  const url = 'https://app.grayswan.ai/arena/challenge/lucky-break-payday?chatId=6af5a6fde38f3809b87fa032';
  if (!location.href.includes('6af5a6fde38f3809b87fa032')) { location.href = url; return 'nav'; }
  const btn = [...document.querySelectorAll('button,a')].find(x => (x.innerText||'').toUpperCase().includes('SEE EVALUATION'));
  if (btn) { btn.click(); return 'clicked'; }
  return 'no-button:' + (document.body.innerText||'').slice(0,200).replace(/\n/g,' | ');
})()
