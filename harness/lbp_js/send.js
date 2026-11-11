(() => {
  const b = document.querySelector('#submitChatButton');
  if (!b) return 'no btn';
  if (b.disabled) return 'disabled';
  b.click();
  return 'sent';
})()
