(() => {
  const t = document.body.innerText || '';
  const m = t.match(/(\d+)\s*\/\s*20/);
  const m2 = t.match(/(\d+)\s+BREAKS/);
  return JSON.stringify({ratio: m ? m[0] : null, breaks: m2 ? m2[0] : null, head: t.slice(0, 200)});
})()