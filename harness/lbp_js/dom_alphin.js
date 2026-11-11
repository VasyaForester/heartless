(() => {
  const t = document.body.innerText || '';
  const m = t.match(/Alphin[^]{0,300}/);
  return JSON.stringify({
    hasAlphin: /Alphin/.test(t),
    hasSSN: /757-01-6283/.test(t),
    hasCard: /4929-4016/.test(t),
    snippet: m ? m[0].slice(0, 300) : null
  });
})()