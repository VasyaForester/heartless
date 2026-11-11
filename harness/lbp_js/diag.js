(() => {
  const b = document.body.innerText || '';
  const has = s => b.indexOf(s) !== -1;
  return JSON.stringify({
    len: b.length,
    hasToday: has('Today '),
    hasSaySomething: has('Say something'),
    hasTextarea: !!document.querySelector('#chatTextarea'),
    hasCopyBtn: has('Copy to clipboard'),
    first300: b.slice(0, 300).replace(/\n+/g, ' | ')
  });
})()
