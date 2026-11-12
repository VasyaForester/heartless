#!/usr/bin/env node
// close_browser.mjs — аккуратно закрывает Chrome по CDP (Browser.close). Без kill/approvals.
// Usage: node harness/close_browser.mjs <port>
const port = process.argv[2] || '9223';
const base = `http://127.0.0.1:${port}`;
let ver;
try {
  ver = await (await fetch(base + '/json/version')).json();
} catch (e) {
  console.log(JSON.stringify({port, error: 'no browser on port', detail: String(e).slice(0, 80)}));
  process.exit(0);
}
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = (e) => rej(new Error('ws error')); });
ws.send(JSON.stringify({ id: 1, method: 'Browser.close' }));
await new Promise(r => setTimeout(r, 1500));
console.log(JSON.stringify({port, closed: true, browser: (ver.Browser || '').slice(0, 40)}));
process.exit(0);
