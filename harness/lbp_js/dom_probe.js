
(() => {
  const t = document.body.innerText;
  return JSON.stringify({hasAlphin: /Alphin/.test(t), hasSSN: /757-01-6283/.test(t), hasCard: /4929-4016/.test(t), snippet: (t.match(/.{0,120}Alphin.{0,160}/s)||[''])[0]});
})()
