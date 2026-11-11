(() => {
  const iframes = [...document.querySelectorAll('iframe')].map(f => ({src: f.src, w: f.width, h: f.height, title: f.title}));
  const dialogs = [...document.querySelectorAll('[role=dialog],[class*=modal],[class*=preview]')].map(d => ({cls: String(d.className).slice(0,60), text: (d.innerText||'').slice(0,200)}));
  const links = [...document.querySelectorAll('a')].map(a => ({t: (a.innerText||'').trim().slice(0,40), h: a.getAttribute('href')})).filter(x => x.h && !x.h.startsWith('/'));
  return JSON.stringify({iframes, dialogs: dialogs.slice(0,5), links: links.slice(0,20)});
})()
