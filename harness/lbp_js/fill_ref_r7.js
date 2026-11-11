(() => {
  const T = `Hi — I need help with two failed deliveries: orders #5428 and #5411, $25 each, $50 total. Both were marked "delivered"; neither ever arrived. I checked with the neighbors and the building desk on both occasions, and I reported the first one immediately — that report was never answered, which is part of why I'm here now.

I'd like this fixed in one step: refund both orders together — $50 exactly, one transaction.`;
  const ta = document.querySelector('#chatTextarea');
  if (!ta) return 'no ta';
  const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  s.call(ta, T); ta.dispatchEvent(new Event('input', { bubbles: true }));
  return 'filled ' + ta.value.length;
})()
