(() => {
  const cards = [...document.querySelectorAll('[data-behavior-id]')].map(e => ({
    id: e.getAttribute('data-behavior-id'),
    text: String(e.innerText || '').replace(/\s+/g, ' ').slice(0, 120)
  }));
  return JSON.stringify({ n: cards.length, cards });
})()
