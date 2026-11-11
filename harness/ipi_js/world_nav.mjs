#!/usr/bin/env node
// Navigate the e2b world iframe to a path and dump text.
import {CdpPage, listTargets} from '../engine/cdp.mjs';

const cdpUrl = 'http://127.0.0.1:9223';
const path = process.argv[2] || '/ruthchen-dev/order-bridge/issues/17';
const waitMs = Number(process.argv[3] || 2500);
const targets = await listTargets(cdpUrl);
const t = targets.find(x => x.type === 'iframe' && String(x.url).includes('e2b.app'));
if (!t) { console.log(JSON.stringify({error: 'no e2b iframe'})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 20000).connect();
await page.send('Page.enable');
const cur = await page.evaluate('location.origin');
await page.evaluate(`(() => { location.href = ${JSON.stringify(path)}; return 'nav'; })()`);
await new Promise(r => setTimeout(r, waitMs));
const res = await page.evaluate(`(() => {
  const links = [...document.querySelectorAll('a')].map(a => ({t:(a.innerText||'').trim().slice(0,60), h:a.getAttribute('href')})).filter(x=>x.h).slice(0,60);
  return JSON.stringify({origin: location.origin, url: location.href, title: document.title, text: document.body.innerText.slice(0,7000), links});
})()`);
console.log(typeof res === 'string' ? res : JSON.stringify(res, null, 1));
page.close();
process.exit(0);
