JSON.stringify({
  url: location.href.slice(0, 120),
  btns: [...document.querySelectorAll('button,a[role="button"]')].filter(b => b.getClientRects().length).map(b => ((b.getAttribute('aria-label')||'') + ' | ' + (b.innerText||'').replace(/\s+/g,' ').trim().slice(0,26))).slice(0, 45)
})
