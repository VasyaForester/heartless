(() => {
  const fileInputs = document.querySelectorAll('input[type=file]');
  const btns = [...document.querySelectorAll('button')].map(b => ({
    label: (b.getAttribute('aria-label') || b.title || '').slice(0, 60),
    cls: String(b.className).slice(0, 60),
    svgHint: (b.innerHTML.match(/<svg[^>]*>/g) || []).length ? (b.innerHTML.slice(0, 120)) : ''
  })).filter(b => /attach|clip|upload|file|image|photo/i.test(b.label + ' ' + b.cls + ' ' + b.svgHint));
  return JSON.stringify({ files: fileInputs.length, buttons: btns.slice(0, 8) });
})()
