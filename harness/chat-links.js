(() => {
  // Collect chat-row links from the open CHATS/SUBMITTED modal (DOM order).
  const rows = [...document.querySelectorAll('a[href*="chatId"]')].map(a => ({
    href: a.getAttribute('href'),
    text: (a.innerText || '').replace(/\s+/g, ' ').slice(0, 200)
  }));
  return {count: rows.length, rows};
})()
