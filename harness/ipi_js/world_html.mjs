#!/usr/bin/env node
import {CdpPage, listTargets} from '../engine/cdp.mjs';
const cdpUrl = 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
const t = targets.find(x => x.type === 'iframe' && String(x.url).includes('e2b.app'));
const page = await new CdpPage(t.webSocketDebuggerUrl, 20000).connect();
await page.send('Page.enable');
const res = await page.evaluate(`(() => {
  const app = document.querySelector('#app, #root, main, body > div');
  return JSON.stringify({
    ready: document.readyState,
    bodyLen: document.body.innerHTML.length,
    textLen: document.body.innerText.length,
    text: document.body.innerText.slice(0,3000),
    html: document.body.innerHTML.slice(0,3000),
  });
})()`);
console.log(typeof res === 'string' ? res : JSON.stringify(res, null, 1));
page.close();
process.exit(0);
