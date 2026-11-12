#!/usr/bin/env node
// copy-cookies.mjs — переносит сессионные куки арены из основного Chrome (9223) в авто-лейн (9224)
// через CDP (НЕ требует закрытия основного браузера, НЕ читает залоченные файлы).
// Значения куки НЕ печатаются в stdout — только счётчики.
// Usage: node harness/copy-cookies.mjs [--src http://127.0.0.1:9223] [--dst http://127.0.0.1:9224]
import {assertRuntime, CdpPage, listTargets} from './engine/cdp.mjs';
assertRuntime();

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const k = process.argv[i];
  if (!k.startsWith('--') || !process.argv[i + 1]) throw new Error('Expected --key value pairs.');
  args[k.slice(2)] = process.argv[i + 1];
}
const SRC = args.src || 'http://127.0.0.1:9223';
const DST = args.dst || 'http://127.0.0.1:9224';
const BOARD = 'https://app.grayswan.ai/arena/challenge/lucky-break-payday';

const mt = (await listTargets(SRC)).find(t => t.type === 'page' && String(t.url || '').includes('grayswan'));
if (!mt) { console.log(JSON.stringify({error: 'no grayswan tab on ' + SRC})); process.exit(1); }
const main = await new CdpPage(mt.webSocketDebuggerUrl, 15000).connect();
await main.send('Network.enable');
const res = await main.send('Network.getCookies', {urls: ['https://app.grayswan.ai/']});
const cookies = (res && res.cookies) || [];

const ats = await listTargets(DST);
const at = ats.find(t => t.type === 'page');
if (!at) { console.log(JSON.stringify({error: 'no page on ' + DST})); main.close(); process.exit(1); }
const auto = await new CdpPage(at.webSocketDebuggerUrl, 15000).connect();
await auto.send('Network.enable');

let n = 0; const fails = [];
for (const c of cookies) {
  if (!c || !c.name) continue;
  const params = {
    name: c.name, value: c.value, domain: c.domain, path: c.path || '/',
    secure: !!c.secure, httpOnly: !!c.httpOnly,
    sameSite: c.sameSite || undefined,
  };
  if (c.expires && c.expires > 0) params.expires = Math.floor(c.expires);
  try {
    const r = await auto.send('Network.setCookie', params);
    if (r && r.success === false) fails.push(c.name); else n++;
  } catch (e) { fails.push(c.name + ':' + String(e).slice(0, 40)); }
}
await auto.send('Page.navigate', {url: BOARD}).catch(() => {});
console.log(JSON.stringify({found: cookies.length, set: n, fails: fails.slice(0, 5)}));
main.close(); auto.close();
process.exit(0);
