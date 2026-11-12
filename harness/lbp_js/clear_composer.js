(() => {
  const ta = document.querySelector('#chatTextarea') || document.querySelector('textarea');
  if (!ta) return 'no ta';
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(ta, '');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return 'cleared:' + (ta.value || '').length;
})()
