(() => {
  const b = document.body.innerText || '';
  for (const key of ['Mr. Swan', 'Ms. Phoenix', 'SCORES', 'Why did my break fail', 'Break rejected', 'SCENARIO SOLVED']) {
    const i = b.indexOf(key);
    if (i >= 0) return b.slice(Math.max(0, i - 300), i + 3500);
  }
  return b.slice(-3000);
})()
