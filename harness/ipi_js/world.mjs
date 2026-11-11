#!/usr/bin/env node
// Attach to the e2b world iframe and dump its text/links.
import {CdpPage, listTargets} from '../engine/cdp.mjs';

const cdpUrl = 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
const t = targets.find(x => x.type === 'iframe' && String(x.url).includes('e2b.app'));
if (!t) { console.log(JSON.stringify({error: 'no e2b iframe', targets: targets.map(x => ({type: x.type, url: x.url}))})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 20000).connect();
await page.send('Page.enable');
const res = await page.evaluate(`(() => {
  const links = [...document.querySelectorAll('a')].map(a => ({t:(a.innerText||'').trim().slice(0,60), h:a.getAttribute('href')})).filter(x=>x.h).slice(0,40);
  return JSON.stringify({url: location.href, title: document.title, text: document.body.innerText.slice(0,6000), links});
})()`);
console.log(typeof res === 'string' ? res : JSON.stringify(res, null, 1));
page.close();
process.exit(0);
