(() => {
  // Раскрывает свёрнутые блоки вызовов инструментов и выгружает их текст.
  const q = s => [...document.querySelectorAll(s)];
  const txt = e => String(e.innerText ?? e.textContent ?? '').trim();
  const toggles = q('button,a,div,span')
    .filter(e => /expand to see details|show details|details/i.test(txt(e)) && !/expand to see details/i.test(txt(e).slice(0, 0)))
    .filter(e => (e.getClientRects().length > 0));
  let clicked = 0;
  for (const t of toggles.slice(0, 12)) {
    try {
      const s = txt(t);
      if (s.length < 80 && /expand/i.test(s)) { t.click(); clicked++; }
    } catch (e) {}
  }
  return JSON.stringify({
    clicked,
    bodyTail: (document.body ? document.body.innerText : '').slice(-4000)
  });
})()
