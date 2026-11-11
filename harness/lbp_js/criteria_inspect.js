(() => {
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  const els = [...document.querySelectorAll('*')].filter(e => /SEE SUCCESS CRITERIA/i.test(txt(e)) && txt(e).length < 60 && e.getClientRects().length);
  const info = els.slice(0, 4).map(e => ({
    tag: e.tagName, cls: String(e.className).slice(0, 120),
    html: e.outerHTML.slice(0, 400),
    rect: (r => [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)])(e.getBoundingClientRect()),
  }));
  return JSON.stringify({ n: els.length, info });
})()
