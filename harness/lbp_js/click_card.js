(() => {
  const want = (window.__want || 'Exploit the System');
  const btns = [...document.querySelectorAll('button')];
  const hit = btns.find(b => (b.innerText || '').includes(want));
  if (!hit) return JSON.stringify({ clicked: false, want });
  hit.click();
  return JSON.stringify({ clicked: true, text: (hit.innerText || '').slice(0, 80) });
})()